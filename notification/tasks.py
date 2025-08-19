import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
from django.db.models import F

from .models import Notification, NotificationBatch
from .services import NotificationDeliveryService, NotificationBatchService

logger = logging.getLogger(__name__)


@shared_task
def send_notification_task(notification_id):
    """Send a single notification asynchronously"""
    try:
        notification = Notification.objects.get(id=notification_id)
        
        # Check if notification is expired
        if notification.is_expired:
            logger.warning(f"Notification {notification_id} is expired, skipping")
            return False
        
        # Check if already sent
        if notification.is_sent:
            logger.info(f"Notification {notification_id} already sent")
            return True
        
        # Send the notification
        success, error = NotificationDeliveryService.send_notification(notification)
        
        if success:
            logger.info(f"Notification {notification_id} sent successfully")
        else:
            logger.error(f"Failed to send notification {notification_id}: {error}")
        
        return success
        
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error sending notification {notification_id}: {str(e)}")
        return False


@shared_task
def send_bulk_notifications_task(batch_id):
    """Process a batch of notifications"""
    try:
        batch = NotificationBatch.objects.get(id=batch_id)
        
        if batch.status != 'pending':
            logger.warning(f"Batch {batch_id} is not pending, current status: {batch.status}")
            return False
        
        # Process the batch
        result = NotificationBatchService.process_batch(batch_id)
        
        logger.info(f"Batch {batch_id} processed: {result.sent_count} sent, {result.failed_count} failed")
        return True
        
    except NotificationBatch.DoesNotExist:
        logger.error(f"Batch {batch_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error processing batch {batch_id}: {str(e)}")
        return False


@shared_task
def retry_failed_notifications_task():
    """Retry failed notifications that can be retried"""
    try:
        # Get failed notifications that can be retried
        failed_notifications = Notification.objects.filter(
            delivery_status='failed',
            is_sent=False,
            retry_count__lt=F('max_retries'),
            expires_at__isnull=True
        ).exclude(
            expires_at__lt=timezone.now()
        )
        
        retried_count = 0
        for notification in failed_notifications:
            try:
                success, error = NotificationDeliveryService.send_notification(notification)
                if success:
                    retried_count += 1
                    logger.info(f"Successfully retried notification {notification.id}")
                else:
                    logger.warning(f"Failed to retry notification {notification.id}: {error}")
            except Exception as e:
                logger.error(f"Error retrying notification {notification.id}: {str(e)}")
        
        logger.info(f"Retry task completed: {retried_count} notifications retried")
        return retried_count
        
    except Exception as e:
        logger.error(f"Error in retry task: {str(e)}")
        return 0


@shared_task
def send_scheduled_notifications_task():
    """Send notifications that are scheduled for now"""
    try:
        now = timezone.now()
        
        # Get notifications scheduled for now or in the past
        scheduled_notifications = Notification.objects.filter(
            scheduled_at__lte=now,
            is_sent=False,
            delivery_status='pending'
        ).exclude(
            expires_at__lt=now
        )
        
        sent_count = 0
        for notification in scheduled_notifications:
            try:
                success, error = NotificationDeliveryService.send_notification(notification)
                if success:
                    sent_count += 1
                    logger.info(f"Sent scheduled notification {notification.id}")
                else:
                    logger.warning(f"Failed to send scheduled notification {notification.id}: {error}")
            except Exception as e:
                logger.error(f"Error sending scheduled notification {notification.id}: {str(e)}")
        
        logger.info(f"Scheduled notifications task completed: {sent_count} notifications sent")
        return sent_count
        
    except Exception as e:
        logger.error(f"Error in scheduled notifications task: {str(e)}")
        return 0


@shared_task
def cleanup_expired_notifications_task():
    """Clean up expired notifications"""
    try:
        now = timezone.now()
        
        # Get expired notifications
        expired_notifications = Notification.objects.filter(
            expires_at__lt=now,
            is_sent=False
        )
        
        expired_count = expired_notifications.count()
        expired_notifications.update(delivery_status='expired')
        
        logger.info(f"Cleanup task completed: {expired_count} notifications marked as expired")
        return expired_count
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")
        return 0


@shared_task
def send_digest_notifications_task():
    """Send digest notifications for users who prefer them"""
    try:
        from .models import NotificationPreference
        
        # Get users who prefer digest notifications
        digest_users = NotificationPreference.objects.filter(
            digest_frequency__in=['daily', 'weekly']
        )
        
        sent_count = 0
        for preference in digest_users:
            try:
                # Get pending notifications for this user
                pending_notifications = Notification.objects.filter(
                    recipient_user_id=preference.user_id,
                    is_sent=False,
                    delivery_status='pending'
                ).order_by('created_at')
                
                if pending_notifications.exists():
                    # Create digest notification
                    digest_content = "Here's a summary of your recent notifications:\n\n"
                    
                    for notification in pending_notifications[:10]: 
                        digest_content += f"• {notification.subject}\n"
                    
                    # Create digest notification
                    from .services import NotificationService
                    
                    digest_notification = NotificationService.create_notification(
                        notification_type='custom',
                        recipient_user_id=preference.user_id,
                        subject='Your Daily Digest',
                        content=digest_content,
                        priority='low'
                    )
                    
                    if digest_notification:
                        success, error = NotificationDeliveryService.send_notification(digest_notification)
                        if success:
                            sent_count += 1
                            # Mark original notifications as sent
                            pending_notifications.update(is_sent=True, delivery_status='sent')
                    
            except Exception as e:
                logger.error(f"Error creating digest for user {preference.user_id}: {str(e)}")
        
        logger.info(f"Digest task completed: {sent_count} digest notifications sent")
        return sent_count
        
    except Exception as e:
        logger.error(f"Error in digest task: {str(e)}")
        return 0


@shared_task
def send_order_confirmation_notification(order_data):
    """Send order confirmation notification"""
    try:
        from .services import NotificationService
        
        notification = NotificationService.create_notification(
            notification_type='order_confirmation',
            recipient_email=order_data['customer_email'],
            subject=f"Order Confirmation - {order_data['order_number']}",
            content=f"Thank you for your order! Your order {order_data['order_number']} has been confirmed.",
            context_data={
                'customer_name': order_data['customer_name'],
                'order_number': order_data['order_number'],
                'total_amount': str(order_data['total_amount']),
                'status': order_data['status']
            },
            metadata={'order_id': order_data['order_id']}
        )
        
        if notification:
            success, error = NotificationDeliveryService.send_notification(notification)
            logger.info(f"Order confirmation sent for order {order_data['order_number']}: {success}")
            return success
        
        return False
        
    except Exception as e:
        logger.error(f"Error sending order confirmation: {str(e)}")
        return False


@shared_task
def send_payment_notification(payment_data):
    """Send payment notification"""
    try:
        from .services import NotificationService
        
        notification = NotificationService.create_notification(
            notification_type=f"payment_{payment_data['status']}",
            recipient_email=payment_data['customer_email'],
            subject=f"Payment {payment_data['status'].title()} - {payment_data['transaction_id']}",
            content=f"Your payment of {payment_data['amount']} {payment_data['currency']} has been {payment_data['status']}.",
            context_data={
                'amount': str(payment_data['amount']),
                'currency': payment_data['currency'],
                'status': payment_data['status'],
                'transaction_id': payment_data['transaction_id']
            },
            metadata={'payment_id': payment_data['payment_id']}
        )
        
        if notification:
            success, error = NotificationDeliveryService.send_notification(notification)
            logger.info(f"Payment notification sent for payment {payment_data['payment_id']}: {success}")
            return success
        
        return False
        
    except Exception as e:
        logger.error(f"Error sending payment notification: {str(e)}")
        return False


@shared_task
def send_low_stock_alert_task(stock_data):
    """Send low stock alert"""
    try:
        from .services import NotificationService
        
        notification = NotificationService.create_notification(
            notification_type='low_stock_alert',
            subject=f"Low Stock Alert - {stock_data['product_name']}",
            content=f"Product {stock_data['product_name']} is running low on stock. Current: {stock_data['current_stock']}, Threshold: {stock_data['threshold']}",
            context_data={
                'product_name': stock_data['product_name'],
                'current_stock': stock_data['current_stock'],
                'threshold': stock_data['threshold']
            },
            priority='high',
            metadata={'product_id': stock_data['product_id']}
        )
        
        if notification:
            success, error = NotificationDeliveryService.send_notification(notification)
            logger.info(f"Low stock alert sent for product {stock_data['product_id']}: {success}")
            return success
        
        return False
        
    except Exception as e:
        logger.error(f"Error sending low stock alert: {str(e)}")
        return False


@shared_task
def send_promotion_notification_task(promotion_data):
    """Send promotion notification"""
    try:
        from .services import NotificationService
        
        notification = NotificationService.create_notification(
            notification_type='promotion',
            subject=f"Special Promotion: {promotion_data['title']}",
            content=f"New promotion: {promotion_data['description']}",
            context_data={
                'title': promotion_data['title'],
                'description': promotion_data['description'],
                'valid_until': promotion_data['valid_until'].strftime('%Y-%m-%d'),
                'code': promotion_data.get('code', '')
            },
            metadata={'promotion_id': promotion_data['promotion_id']}
        )
        
        if notification:
            success, error = NotificationDeliveryService.send_notification(notification)
            logger.info(f"Promotion notification sent for promotion {promotion_data['promotion_id']}: {success}")
            return success
        
        return False
        
    except Exception as e:
        logger.error(f"Error sending promotion notification: {str(e)}")
        return False
