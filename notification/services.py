import json
import logging
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.db.models import Q, F, Count, Avg
from django.core.cache import cache
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from .models import (
    Notification, NotificationTemplate, NotificationChannel, NotificationDelivery,
    NotificationPreference, NotificationLog, NotificationBatch
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Main service for notification operations"""
    
    @staticmethod
    def create_notification(
        notification_type,
        recipient_email=None,
        recipient_phone=None,
        recipient_user_id=None,
        template_id=None,
        channel_id=None,
        subject=None,
        content=None,
        html_content=None,
        context_data=None,
        priority='normal',
        scheduled_at=None,
        expires_at=None,
        metadata=None
    ):
        """Create a new notification"""
        try:
            # Get template and channel
            template = None
            if template_id:
                template = NotificationTemplate.objects.get(id=template_id, is_active=True)
            
            channel = None
            if channel_id:
                channel = NotificationChannel.objects.get(id=channel_id, is_active=True)
            else:
                # Get default channel based on type
                if recipient_email:
                    channel = NotificationChannel.objects.filter(
                        channel_type='email', is_active=True
                    ).first()
                elif recipient_phone:
                    channel = NotificationChannel.objects.filter(
                        channel_type='sms', is_active=True
                    ).first()
            
            if not channel:
                raise ValueError("No suitable channel found")
            
            # Render template if provided
            if template and context_data:
                subject = subject or NotificationService.render_template(template.subject, context_data)
                content = content or NotificationService.render_template(template.content, context_data)
                html_content = html_content or NotificationService.render_template(template.html_content, context_data)
            
            # Check user preferences
            if recipient_user_id:
                preferences = NotificationPreference.objects.filter(user_id=recipient_user_id).first()
                if preferences:
                    if not NotificationService.should_send_notification(preferences, notification_type, channel.channel_type):
                        logger.info(f"Notification blocked by user preferences for user {recipient_user_id}")
                        return None
            
            # Check rate limiting
            if not NotificationService.check_rate_limit(channel, recipient_email or recipient_phone):
                logger.warning(f"Rate limit exceeded for {channel.name}")
                return None
            
            notification = Notification.objects.create(
                notification_type=notification_type,
                template=template,
                channel=channel,
                recipient_email=recipient_email,
                recipient_phone=recipient_phone,
                recipient_user_id=recipient_user_id,
                subject=subject,
                content=content,
                html_content=html_content,
                priority=priority,
                context_data=context_data or {},
                metadata=metadata or {},
                scheduled_at=scheduled_at,
                expires_at=expires_at
            )
            
            # Log the creation
            NotificationLog.objects.create(
                level='info',
                message=f"Notification created: {notification_type}",
                notification=notification,
                channel=channel,
                user_id=recipient_user_id
            )
            
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            NotificationLog.objects.create(
                level='error',
                message=f"Failed to create notification: {str(e)}",
                context_data={'notification_type': notification_type, 'error': str(e)}
            )
            raise
    
    @staticmethod
    def render_template(template_content, context_data):
        """Render template with context data"""
        if not template_content:
            return ""
        
        try:
            # Simple template rendering - replace {{variable}} with values
            rendered = template_content
            for key, value in context_data.items():
                placeholder = f"{{{{{key}}}}}"
                rendered = rendered.replace(placeholder, str(value))
            
            return rendered
        except Exception as e:
            logger.error(f"Error rendering template: {str(e)}")
            return template_content
    
    @staticmethod
    def should_send_notification(preferences, notification_type, channel_type):
        """Check if notification should be sent based on user preferences"""
        if channel_type == 'email':
            if not preferences.email_enabled:
                return False
            
            if notification_type in ['order_confirmation', 'order_shipped', 'order_delivered']:
                return preferences.email_order_updates
            elif notification_type in ['payment_success', 'payment_failed', 'refund_processed']:
                return preferences.email_payment_updates
            elif notification_type == 'promotion':
                return preferences.email_promotions
            elif notification_type == 'welcome':
                return preferences.email_newsletter
        
        elif channel_type == 'sms':
            if not preferences.sms_enabled:
                return False
            
            if notification_type in ['order_confirmation', 'order_shipped', 'order_delivered']:
                return preferences.sms_order_updates
            elif notification_type in ['payment_success', 'payment_failed', 'refund_processed']:
                return preferences.sms_payment_updates
            elif notification_type == 'promotion':
                return preferences.sms_promotions
        
        elif channel_type == 'push':
            if not preferences.push_enabled:
                return False
            
            if notification_type in ['order_confirmation', 'order_shipped', 'order_delivered']:
                return preferences.push_order_updates
            elif notification_type in ['payment_success', 'payment_failed', 'refund_processed']:
                return preferences.push_payment_updates
            elif notification_type == 'promotion':
                return preferences.push_promotions
        
        return True
    
    @staticmethod
    def check_rate_limit(channel, recipient):
        """Check rate limiting for the channel and recipient"""
        cache_key = f"rate_limit:{channel.id}:{recipient}"
        
        # Check hourly limit
        hourly_count = cache.get(f"{cache_key}:hourly", 0)
        if hourly_count >= channel.rate_limit_per_hour:
            return False
        
        # Check daily limit
        daily_count = cache.get(f"{cache_key}:daily", 0)
        if daily_count >= channel.rate_limit_per_day:
            return False
        
        return True
    
    @staticmethod
    def update_rate_limit(channel, recipient):
        """Update rate limit counters"""
        cache_key = f"rate_limit:{channel.id}:{recipient}"
        
        # Update hourly counter
        hourly_count = cache.get(f"{cache_key}:hourly", 0) + 1
        cache.set(f"{cache_key}:hourly", hourly_count, 3600)  # 1 hour
        
        # Update daily counter
        daily_count = cache.get(f"{cache_key}:daily", 0) + 1
        cache.set(f"{cache_key}:daily", daily_count, 86400)  # 24 hours


class NotificationDeliveryService:
    """Service for handling notification delivery"""
    
    @staticmethod
    def send_notification(notification):
        """Send a notification through its channel"""
        try:
            delivery = NotificationDelivery.objects.create(
                notification=notification,
                attempt_number=notification.retry_count + 1
            )
            
            success = False
            error_message = ""
            
            if notification.channel.channel_type == 'email':
                success, error_message = NotificationDeliveryService.send_email(notification)
            elif notification.channel.channel_type == 'sms':
                success, error_message = NotificationDeliveryService.send_sms(notification)
            elif notification.channel.channel_type == 'webhook':
                success, error_message = NotificationDeliveryService.send_webhook(notification)
            elif notification.channel.channel_type == 'push':
                success, error_message = NotificationDeliveryService.send_push(notification)
            
            # Update delivery record
            if success:
                delivery.status = 'sent'
                delivery.sent_at = timezone.now()
                notification.is_sent = True
                notification.sent_at = timezone.now()
                notification.delivery_status = 'sent'
                notification.error_message = ""
            else:
                delivery.status = 'failed'
                delivery.error_message = error_message
                notification.delivery_status = 'failed'
                notification.error_message = error_message
                notification.retry_count += 1
            
            notification.save()
            delivery.save()
            
            # Update rate limit
            recipient = notification.recipient_email or notification.recipient_phone
            NotificationService.update_rate_limit(notification.channel, recipient)
            
            # Log the delivery attempt
            NotificationLog.objects.create(
                level='info' if success else 'error',
                message=f"Notification delivery {'successful' if success else 'failed'}",
                notification=notification,
                channel=notification.channel,
                context_data={'success': success, 'error': error_message}
            )
            
            return success, error_message
            
        except Exception as e:
            logger.error(f"Error sending notification {notification.id}: {str(e)}")
            return False, str(e)
    
    @staticmethod
    def send_email(notification):
        """Send email notification"""
        try:
            # Use Django's email backend
            if notification.html_content:
                # Send HTML email
                from django.core.mail import EmailMultiAlternatives
                email = EmailMultiAlternatives(
                    subject=notification.subject,
                    body=notification.content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[notification.recipient_email]
                )
                email.attach_alternative(notification.html_content, "text/html")
                email.send()
            else:
                # Send plain text email
                send_mail(
                    subject=notification.subject,
                    message=notification.content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[notification.recipient_email],
                    fail_silently=False
                )
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Email delivery failed: {str(e)}")
            return False, str(e)
    
    @staticmethod
    def send_sms(notification):
        """Send SMS notification (mock implementation)"""
        try:
            # Mock SMS sending - in production, integrate with SMS provider
            logger.info(f"SMS sent to {notification.recipient_phone}: {notification.content}")
            
            # Simulate provider response
            provider_message_id = f"sms_{uuid.uuid4().hex[:16]}"
            
            return True, ""
            
        except Exception as e:
            logger.error(f"SMS delivery failed: {str(e)}")
            return False, str(e)
    
    @staticmethod
    def send_webhook(notification):
        """Send webhook notification"""
        try:
            channel = notification.channel
            
            payload = {
                'notification_id': str(notification.id),
                'type': notification.notification_type,
                'subject': notification.subject,
                'content': notification.content,
                'recipient_email': notification.recipient_email,
                'recipient_phone': notification.recipient_phone,
                'metadata': notification.metadata,
                'timestamp': timezone.now().isoformat()
            }
            
            headers = channel.webhook_headers or {}
            headers['Content-Type'] = 'application/json'
            
            response = requests.post(
                channel.webhook_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code in [200, 201, 202]:
                return True, ""
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except Exception as e:
            logger.error(f"Webhook delivery failed: {str(e)}")
            return False, str(e)
    
    @staticmethod
    def send_push(notification):
        """Send push notification (mock implementation)"""
        try:
            # Mock push notification - in production, integrate with FCM, APNS, etc.
            logger.info(f"Push notification sent to user {notification.recipient_user_id}: {notification.content}")
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Push notification delivery failed: {str(e)}")
            return False, str(e)


class NotificationBatchService:
    """Service for handling batch notifications"""
    
    @staticmethod
    def create_batch_notification(batch_data):
        """Create a batch notification"""
        try:
            batch = NotificationBatch.objects.create(
                name=batch_data['name'],
                template_id=batch_data['template_id'],
                channel_id=batch_data['channel_id'],
                scheduled_at=batch_data.get('scheduled_at'),
                batch_size=batch_data.get('batch_size', 100),
                delay_between_batches=batch_data.get('delay_between_batches', 60)
            )
            
            # Create individual notifications for each recipient
            recipients = batch_data['recipients']
            batch.total_recipients = len(recipients)
            batch.save()
            
            notifications_created = 0
            for recipient in recipients:
                try:
                    notification = NotificationService.create_notification(
                        notification_type='custom',
                        recipient_email=recipient.get('email'),
                        recipient_phone=recipient.get('phone'),
                        recipient_user_id=recipient.get('user_id'),
                        template_id=batch_data['template_id'],
                        channel_id=batch_data['channel_id'],
                        context_data=recipient.get('context_data', {}),
                        scheduled_at=batch_data.get('scheduled_at'),
                        metadata={'batch_id': str(batch.id)}
                    )
                    if notification:
                        notifications_created += 1
                except Exception as e:
                    logger.error(f"Failed to create notification for recipient {recipient}: {str(e)}")
            
            return batch
            
        except Exception as e:
            logger.error(f"Error creating batch notification: {str(e)}")
            raise
    
    @staticmethod
    def process_batch(batch_id):
        """Process a batch of notifications"""
        try:
            batch = NotificationBatch.objects.get(id=batch_id)
            batch.status = 'processing'
            batch.started_at = timezone.now()
            batch.save()
            
            # Get pending notifications for this batch
            notifications = Notification.objects.filter(
                metadata__batch_id=str(batch.id),
                is_sent=False
            ).order_by('created_at')
            
            sent_count = 0
            failed_count = 0
            
            for notification in notifications:
                try:
                    success, error = NotificationDeliveryService.send_notification(notification)
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                    
                    # Add delay between notifications
                    if sent_count % batch.batch_size == 0:
                        import time
                        time.sleep(batch.delay_between_batches)
                        
                except Exception as e:
                    logger.error(f"Error processing notification {notification.id}: {str(e)}")
                    failed_count += 1
            
            # Update batch status
            batch.sent_count = sent_count
            batch.failed_count = failed_count
            batch.status = 'completed'
            batch.completed_at = timezone.now()
            batch.save()
            
            return batch
            
        except Exception as e:
            logger.error(f"Error processing batch {batch_id}: {str(e)}")
            batch.status = 'failed'
            batch.save()
            raise


class NotificationStatsService:
    """Service for notification statistics"""
    
    @staticmethod
    def get_notification_stats(date_from=None, date_to=None):
        """Get comprehensive notification statistics"""
        if not date_from:
            date_from = timezone.now() - timedelta(days=30)
        if not date_to:
            date_to = timezone.now()
        
        # Base queryset
        notifications = Notification.objects.filter(
            created_at__range=(date_from, date_to)
        )
        
        # Basic counts
        total_notifications = notifications.count()
        sent_notifications = notifications.filter(is_sent=True).count()
        failed_notifications = notifications.filter(delivery_status='failed').count()
        pending_notifications = notifications.filter(is_sent=False, delivery_status='pending').count()
        
        # Delivery rate
        delivery_rate = (sent_notifications / total_notifications * 100) if total_notifications > 0 else 0
        
        # Average delivery time
        successful_deliveries = NotificationDelivery.objects.filter(
            status='sent',
            sent_at__range=(date_from, date_to)
        )
        avg_delivery_time = successful_deliveries.aggregate(
            avg_time=Avg(F('sent_at') - F('notification__created_at'))
        )['avg_time']
        
        # By type
        notifications_by_type = notifications.values('notification_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # By channel
        notifications_by_channel = notifications.values('channel__name').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # By status
        notifications_by_status = notifications.values('delivery_status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Time series data
        today = timezone.now().date()
        notifications_today = notifications.filter(created_at__date=today).count()
        notifications_this_week = notifications.filter(
            created_at__gte=today - timedelta(days=7)
        ).count()
        notifications_this_month = notifications.filter(
            created_at__gte=today - timedelta(days=30)
        ).count()
        
        return {
            'total_notifications': total_notifications,
            'sent_notifications': sent_notifications,
            'failed_notifications': failed_notifications,
            'pending_notifications': pending_notifications,
            'delivery_rate': round(delivery_rate, 2),
            'average_delivery_time': avg_delivery_time.total_seconds() if avg_delivery_time else 0,
            'notifications_by_type': {item['notification_type']: item['count'] for item in notifications_by_type},
            'notifications_by_channel': {item['channel__name']: item['count'] for item in notifications_by_channel},
            'notifications_by_status': {item['delivery_status']: item['count'] for item in notifications_by_status},
            'notifications_today': notifications_today,
            'notifications_this_week': notifications_this_week,
            'notifications_this_month': notifications_this_month,
        }
    
    @staticmethod
    def get_channel_stats(channel_id, date_from=None, date_to=None):
        """Get statistics for a specific channel"""
        if not date_from:
            date_from = timezone.now() - timedelta(days=30)
        if not date_to:
            date_to = timezone.now()
        
        notifications = Notification.objects.filter(
            channel_id=channel_id,
            created_at__range=(date_from, date_to)
        )
        
        total = notifications.count()
        sent = notifications.filter(is_sent=True).count()
        failed = notifications.filter(delivery_status='failed').count()
        
        return {
            'total': total,
            'sent': sent,
            'failed': failed,
            'success_rate': (sent / total * 100) if total > 0 else 0,
            'failure_rate': (failed / total * 100) if total > 0 else 0,
        }


class NotificationPreferenceService:
    """Service for managing notification preferences"""
    
    @staticmethod
    def get_or_create_preferences(user_id):
        """Get or create notification preferences for a user"""
        preferences, created = NotificationPreference.objects.get_or_create(
            user_id=user_id,
            defaults={
                'email_enabled': True,
                'email_order_updates': True,
                'email_payment_updates': True,
                'email_promotions': True,
                'email_newsletter': False,
                'sms_enabled': False,
                'sms_order_updates': False,
                'sms_payment_updates': False,
                'sms_promotions': False,
                'push_enabled': True,
                'push_order_updates': True,
                'push_payment_updates': True,
                'push_promotions': False,
                'digest_frequency': 'immediate'
            }
        )
        return preferences
    
    @staticmethod
    def update_preferences(user_id, preferences_data):
        """Update notification preferences for a user"""
        preferences = NotificationPreferenceService.get_or_create_preferences(user_id)
        
        for field, value in preferences_data.items():
            if hasattr(preferences, field):
                setattr(preferences, field, value)
        
        preferences.save()
        return preferences
    
    @staticmethod
    def bulk_update_preferences(user_ids, preferences_data):
        """Bulk update preferences for multiple users"""
        updated_count = 0
        
        for user_id in user_ids:
            try:
                preferences = NotificationPreferenceService.get_or_create_preferences(user_id)
                
                for field, value in preferences_data.items():
                    if hasattr(preferences, field):
                        setattr(preferences, field, value)
                
                preferences.save()
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to update preferences for user {user_id}: {str(e)}")
        
        return updated_count
