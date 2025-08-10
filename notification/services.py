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
from typing import List, Dict, Any, Optional, Union
from django.db import models, transaction
from django.db.models import Q, Count, Avg, F, Sum, Case, When, Value, IntegerField
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from .models import (
    Notification, NotificationTemplate, NotificationPreference,
    NotificationDelivery, NotificationBatch, NotificationStats
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications with optimized query patterns."""
    
    # Class-level cache for templates and preferences
    _template_cache = {}
    _preference_cache = {}
    _cache_ttl = 300  # 5 minutes
    
    @classmethod
    def _get_cached_template(cls, template_id: int) -> Optional[NotificationTemplate]:
        """Get cached template to avoid repeated database queries."""
        cache_key = f"notification_template_{template_id}"
        if cache_key not in cls._template_cache:
            template = NotificationTemplate.objects.select_related('category').get(id=template_id)
            cls._template_cache[cache_key] = template
            # Clear old cache entries periodically
            if len(cls._template_cache) > 100:
                cls._template_cache.clear()
        return cls._template_cache[cache_key]
    
    @classmethod
    def _get_cached_preferences(cls, user_id: int, category: str) -> Optional[NotificationPreference]:
        """Get cached user preferences to avoid repeated database queries."""
        cache_key = f"notification_pref_{user_id}_{category}"
        if cache_key not in cls._preference_cache:
            try:
                pref = NotificationPreference.objects.select_related('user').get(
                    user_id=user_id, category=category
                )
                cls._preference_cache[cache_key] = pref
            except NotificationPreference.DoesNotExist:
                cls._preference_cache[cache_key] = None
            # Clear old cache entries periodically
            if len(cls._preference_cache) > 200:
                cls._preference_cache.clear()
        return cls._preference_cache[cache_key]
    
    @classmethod
    def create_notification(
        cls,
        user_id: int,
        template_id: int,
        context: Dict[str, Any],
        priority: str = 'normal',
        category: str = 'general'
    ) -> Notification:
        """Create a notification with optimized template and preference lookup."""
        # Use cached template and preferences
        template = cls._get_cached_template(template_id)
        preferences = cls._get_cached_preferences(user_id, category)
        
        if preferences and not preferences.enabled:
            logger.info(f"Notifications disabled for user {user_id} in category {category}")
            return None
        
        # Check rate limiting using cache
        rate_limit_key = f"notification_rate_limit_{user_id}_{category}"
        if cache.get(rate_limit_key):
            logger.warning(f"Rate limit exceeded for user {user_id} in category {category}")
            return None
        
        # Set rate limit (1 notification per minute per category)
        cache.set(rate_limit_key, True, 60)
        
        notification = Notification.objects.create(
            user_id=user_id,
            template=template,
            context=context,
            priority=priority,
            category=category,
            created_at=timezone.now()
        )
        
        # Clear preference cache for this user
        cls._clear_user_preference_cache(user_id)
        
        return notification
    
    @classmethod
    def bulk_create_notifications(
        cls,
        notifications_data: List[Dict[str, Any]]
    ) -> List[Notification]:
        """Bulk create notifications for better performance."""
        notifications = []
        templates_cache = {}
        preferences_cache = {}
        
        # Pre-fetch all templates and preferences in single queries
        template_ids = list(set(data['template_id'] for data in notifications_data))
        user_ids = list(set(data['user_id'] for data in notifications_data))
        categories = list(set(data.get('category', 'general') for data in notifications_data))
        
        templates = {
            t.id: t for t in NotificationTemplate.objects.select_related('category').filter(
                id__in=template_ids
            )
        }
        
        preferences = {
            (p.user_id, p.category): p for p in NotificationPreference.objects.select_related('user').filter(
                user_id__in=user_ids,
                category__in=categories
            )
        }
        
        for data in notifications_data:
            template = templates.get(data['template_id'])
            if not template:
                continue
                
            category = data.get('category', 'general')
            user_id = data['user_id']
            
            pref_key = (user_id, category)
            if pref_key in preferences and not preferences[pref_key].enabled:
                continue
            
            # Check rate limiting
            rate_limit_key = f"notification_rate_limit_{user_id}_{category}"
            if cache.get(rate_limit_key):
                continue
            
            cache.set(rate_limit_key, True, 60)
            
            notifications.append(Notification(
                user_id=user_id,
                template=template,
                context=data.get('context', {}),
                priority=data.get('priority', 'normal'),
                category=category,
                created_at=timezone.now()
            ))
        
        if notifications:
            created_notifications = Notification.objects.bulk_create(notifications)
            # Clear preference cache for affected users
            affected_users = list(set(n.user_id for n in created_notifications))
            cls._clear_user_preference_cache(affected_users)
            return created_notifications
        
        return []
    
    @classmethod
    def _clear_user_preference_cache(cls, user_ids: Union[int, List[int]]):
        """Clear preference cache for specific users."""
        if isinstance(user_ids, int):
            user_ids = [user_ids]
        
        for user_id in user_ids:
            for category in ['general', 'order', 'payment', 'inventory', 'security']:
                cache_key = f"notification_pref_{user_id}_{category}"
                if cache_key in cls._preference_cache:
                    del cls._preference_cache[cache_key]
    
    @classmethod
    def render_notification(cls, notification_id: int) -> str:
        """Render notification content with template caching."""
        try:
            notification = Notification.objects.select_related('template').get(id=notification_id)
            template = cls._get_cached_template(notification.template.id)
            
            # Simple template rendering (in production, use a proper template engine)
            content = template.content
            for key, value in notification.context.items():
                content = content.replace(f"{{{{{key}}}}}", str(value))
            
            return content
        except Notification.DoesNotExist:
            return "Notification not found"
    
    @classmethod
    def check_preferences(cls, user_id: int, category: str) -> bool:
        """Check user notification preferences with caching."""
        preferences = cls._get_cached_preferences(user_id, category)
        return preferences.enabled if preferences else True
    
    @classmethod
    def get_user_notifications(
        cls,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        category: Optional[str] = None,
        read: Optional[bool] = None
    ) -> List[Notification]:
        """Get user notifications with optimized querying."""
        queryset = Notification.objects.select_related('template', 'template__category').filter(
            user_id=user_id
        )
        
        # Apply filters efficiently
        if category:
            queryset = queryset.filter(category=category)
        if read is not None:
            queryset = queryset.filter(is_read=read)
        
        return list(queryset.order_by('-created_at')[offset:offset + limit])
    
    @classmethod
    def mark_as_read(cls, notification_ids: List[int]) -> int:
        """Mark multiple notifications as read using bulk update."""
        if not notification_ids:
            return 0
        
        updated_count = Notification.objects.filter(
            id__in=notification_ids
        ).update(is_read=True, read_at=timezone.now())
        
        return updated_count
    
    @classmethod
    def delete_notifications(cls, notification_ids: List[int]) -> int:
        """Delete multiple notifications efficiently."""
        if not notification_ids:
            return 0
        
        deleted_count, _ = Notification.objects.filter(
            id__in=notification_ids
        ).delete()
        
        return deleted_count


class NotificationDeliveryService:
    """Service for delivering notifications via various channels."""
    
    def __init__(self):
        self.delivery_methods = {
            'email': self._send_email,
            'sms': self._send_sms,
            'push': self._send_push,
            'webhook': self._send_webhook
        }
    
    def deliver_notification(
        self,
        notification: Notification,
        method: str,
        delivery_config: Dict[str, Any]
    ) -> NotificationDelivery:
        """Deliver notification via specified method."""
        if method not in self.delivery_methods:
            raise ValueError(f"Unsupported delivery method: {method}")
        
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            method=method,
            status='pending',
            delivery_config=delivery_config
        )
        
        try:
            # Attempt delivery
            success = self.delivery_methods[method](notification, delivery_config)
            delivery.status = 'delivered' if success else 'failed'
            delivery.delivered_at = timezone.now() if success else None
            delivery.save(update_fields=['status', 'delivered_at'])
        except Exception as e:
            delivery.status = 'failed'
            delivery.error_message = str(e)
            delivery.save(update_fields=['status', 'error_message'])
            logger.error(f"Failed to deliver notification {notification.id}: {e}")
        
        return delivery
    
    def bulk_deliver_notifications(
        self,
        notifications: List[Notification],
        method: str,
        delivery_config: Dict[str, Any]
    ) -> List[NotificationDelivery]:
        """Bulk deliver notifications for better performance."""
        if not notifications:
            return []
        
        # Create delivery records in bulk
        deliveries = [
            NotificationDelivery(
                notification=notification,
                method=method,
                status='pending',
                delivery_config=delivery_config
            )
            for notification in notifications
        ]
        
        created_deliveries = NotificationDelivery.objects.bulk_create(deliveries)
        
        # Process deliveries
        for delivery in created_deliveries:
            try:
                success = self.delivery_methods[method](delivery.notification, delivery_config)
                delivery.status = 'delivered' if success else 'failed'
                delivery.delivered_at = timezone.now() if success else None
            except Exception as e:
                delivery.status = 'failed'
                delivery.error_message = str(e)
                logger.error(f"Failed to deliver notification {delivery.notification.id}: {e}")
        
        # Bulk update delivery statuses
        NotificationDelivery.objects.bulk_update(
            created_deliveries,
            ['status', 'delivered_at', 'error_message']
        )
        
        return created_deliveries
    
    def _send_email(self, notification: Notification, config: Dict[str, Any]) -> bool:
        """Send notification via email."""
        # Implementation would integrate with email service
        logger.info(f"Sending email notification {notification.id}")
        return True
    
    def _send_sms(self, notification: Notification, config: Dict[str, Any]) -> bool:
        """Send notification via SMS."""
        # Implementation would integrate with SMS service
        logger.info(f"Sending SMS notification {notification.id}")
        return True
    
    def _send_push(self, notification: Notification, config: Dict[str, Any]) -> bool:
        """Send push notification."""
        # Implementation would integrate with push notification service
        logger.info(f"Sending push notification {notification.id}")
        return True
    
    def _send_webhook(self, notification: Notification, config: Dict[str, Any]) -> bool:
        """Send notification via webhook."""
        # Implementation would integrate with webhook service
        logger.info(f"Sending webhook notification {notification.id}")
        return True


class NotificationBatchService:
    """Service for managing batch notifications."""
    
    def create_batch(
        self,
        template_id: int,
        user_ids: List[int],
        context: Dict[str, Any],
        category: str = 'general'
    ) -> NotificationBatch:
        """Create a batch of notifications."""
        batch = NotificationBatch.objects.create(
            template_id=template_id,
            context=context,
            category=category,
            total_users=len(user_ids),
            status='pending'
        )
        
        # Create notifications in bulk
        notifications = [
            Notification(
                user_id=user_id,
                template_id=template_id,
                context=context,
                category=category,
                created_at=timezone.now()
            )
            for user_id in user_ids
        ]
        
        Notification.objects.bulk_create(notifications)
        batch.status = 'completed'
        batch.completed_at = timezone.now()
        batch.save(update_fields=['status', 'completed_at'])
        
        return batch
    
    def process_batch(self, batch_id: int) -> bool:
        """Process a batch of notifications."""
        try:
            batch = NotificationBatch.objects.select_related('template').get(id=batch_id)
            notifications = Notification.objects.filter(
                template_id=batch.template_id,
                category=batch.category,
                created_at__gte=batch.created_at
            )
            
            # Process notifications in chunks for memory efficiency
            chunk_size = 1000
            for i in range(0, len(notifications), chunk_size):
                chunk = notifications[i:i + chunk_size]
                # Process chunk (e.g., send to delivery service)
                logger.info(f"Processing batch {batch_id} chunk {i//chunk_size + 1}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to process batch {batch_id}: {e}")
            return False


class NotificationStatsService:
    """Service for notification statistics with optimized queries."""
    
    # Cache for statistics
    _stats_cache = {}
    _cache_ttl = 300  # 5 minutes
    
    @classmethod
    def get_notification_stats(
        cls,
        user_id: Optional[int] = None,
        category: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get comprehensive notification statistics using optimized queries."""
        cache_key = f"notification_stats_{user_id}_{category}_{start_date}_{end_date}"
        
        if cache_key in cls._stats_cache:
            return cls._stats_cache[cache_key]
        
        # Build base queryset
        base_filters = {}
        if user_id:
            base_filters['user_id'] = user_id
        if category:
            base_filters['category'] = category
        if start_date:
            base_filters['created_at__gte'] = start_date
        if end_date:
            base_filters['created_at__lte'] = end_date
        
        # Use aggregate for efficient statistics calculation
        stats = Notification.objects.filter(**base_filters).aggregate(
            total_notifications=Count('id'),
            unread_count=Count('id', filter=Q(is_read=False)),
            high_priority=Count('id', filter=Q(priority='high')),
            medium_priority=Count('id', filter=Q(priority='medium')),
            low_priority=Count('id', filter=Q(priority='low'))
        )
        
        # Get category distribution
        category_stats = Notification.objects.filter(**base_filters).values('category').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Get delivery statistics
        delivery_stats = NotificationDelivery.objects.filter(
            notification__in=Notification.objects.filter(**base_filters)
        ).values('status').annotate(
            count=Count('id')
        )
        
        # Get time-based statistics
        time_stats = Notification.objects.filter(**base_filters).extra(
            select={'hour': 'EXTRACT(hour FROM created_at)'}
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        result = {
            'overview': stats,
            'category_distribution': list(category_stats),
            'delivery_status': list(delivery_stats),
            'hourly_distribution': list(time_stats),
            'generated_at': timezone.now()
        }
        
        # Cache the result
        cls._stats_cache[cache_key] = result
        
        # Clear old cache entries
        if len(cls._stats_cache) > 50:
            cls._stats_cache.clear()
        
        return result
    
    @classmethod
    def get_user_notification_summary(cls, user_id: int) -> Dict[str, Any]:
        """Get user-specific notification summary."""
        cache_key = f"user_notification_summary_{user_id}"
        
        if cache_key in cls._stats_cache:
            return cls._stats_cache[cache_key]
        
        # Single query for user summary
        summary = Notification.objects.filter(user_id=user_id).aggregate(
            total=Count('id'),
            unread=Count('id', filter=Q(is_read=False)),
            today=Count('id', filter=Q(created_at__date=timezone.now().date())),
            this_week=Count('id', filter=Q(created_at__gte=timezone.now() - timedelta(days=7))),
            high_priority=Count('id', filter=Q(priority='high', is_read=False))
        )
        
        # Get recent categories
        recent_categories = Notification.objects.filter(
            user_id=user_id
        ).values('category').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        result = {
            'summary': summary,
            'recent_categories': list(recent_categories)
        }
        
        cls._stats_cache[cache_key] = result
        return result
    
    @classmethod
    def clear_stats_cache(cls):
        """Clear statistics cache."""
        cls._stats_cache.clear()


class NotificationPreferenceService:
    """Service for managing notification preferences."""
    
    def get_user_preferences(self, user_id: int) -> List[NotificationPreference]:
        """Get all preferences for a user."""
        return list(NotificationPreference.objects.select_related('user').filter(
            user_id=user_id
        ))
    
    def update_preferences(
        self,
        user_id: int,
        preferences: Dict[str, Dict[str, Any]]
    ) -> int:
        """Update multiple user preferences efficiently."""
        updated_count = 0
        
        for category, settings in preferences.items():
            pref, created = NotificationPreference.objects.get_or_create(
                user_id=user_id,
                category=category,
                defaults={
                    'enabled': settings.get('enabled', True),
                    'email_enabled': settings.get('email_enabled', True),
                    'sms_enabled': settings.get('sms_enabled', False),
                    'push_enabled': settings.get('push_enabled', True),
                    'webhook_enabled': settings.get('webhook_enabled', False)
                }
            )
            
            if not created:
                # Update existing preference
                for field, value in settings.items():
                    if hasattr(pref, field):
                        setattr(pref, field, value)
                pref.save(update_fields=list(settings.keys()))
                updated_count += 1
            else:
                updated_count += 1
        
        # Clear preference cache for this user
        NotificationService._clear_user_preference_cache(user_id)
        
        return updated_count
    
    def bulk_update_preferences(
        self,
        user_preferences: List[Dict[str, Any]]
    ) -> int:
        """Bulk update preferences for multiple users."""
        if not user_preferences:
            return 0
        
        updated_count = 0
        
        for user_data in user_preferences:
            user_id = user_data['user_id']
            preferences = user_data['preferences']
            
            updated_count += self.update_preferences(user_id, preferences)
        
        return updated_count
