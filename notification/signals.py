from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Notification, NotificationDelivery, NotificationLog


@receiver(post_save, sender=Notification)
def notification_post_save(sender, instance, created, **kwargs):
    """Handle post-save actions for notifications"""
    if created:
        # Log notification creation
        NotificationLog.objects.create(
            level='info',
            message=f"Notification created: {instance.notification_type}",
            notification=instance,
            channel=instance.channel,
            user_id=instance.recipient_user_id
        )
    
    # If notification status changed to sent, log it
    if instance.is_sent and instance.sent_at:
        NotificationLog.objects.create(
            level='info',
            message=f"Notification sent successfully",
            notification=instance,
            channel=instance.channel,
            user_id=instance.recipient_user_id
        )


@receiver(post_save, sender=NotificationDelivery)
def delivery_post_save(sender, instance, created, **kwargs):
    """Handle post-save actions for notification deliveries"""
    if created:
        # Log delivery attempt
        level = 'info' if instance.status == 'sent' else 'error'
        message = f"Delivery attempt {instance.attempt_number}: {instance.status}"
        
        NotificationLog.objects.create(
            level=level,
            message=message,
            notification=instance.notification,
            channel=instance.notification.channel,
            user_id=instance.notification.recipient_user_id,
            context_data={
                'attempt_number': instance.attempt_number,
                'status': instance.status,
                'error_message': instance.error_message
            }
        )


@receiver(pre_save, sender=Notification)
def notification_pre_save(sender, instance, **kwargs):
    """Handle pre-save actions for notifications"""
    if instance.pk:
        # Check if status changed
        try:
            old_instance = Notification.objects.get(pk=instance.pk)
            if old_instance.delivery_status != instance.delivery_status:
                # Log status change
                NotificationLog.objects.create(
                    level='info',
                    message=f"Notification status changed from {old_instance.delivery_status} to {instance.delivery_status}",
                    notification=instance,
                    channel=instance.channel,
                    user_id=instance.recipient_user_id,
                    context_data={
                        'old_status': old_instance.delivery_status,
                        'new_status': instance.delivery_status
                    }
                )
        except Notification.DoesNotExist:
            pass
