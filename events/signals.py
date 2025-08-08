from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Event, EventDelivery
from .services import EventService


@receiver(post_save, sender=Event)
def process_event_on_save(sender, instance, created, **kwargs):
    """Process event when it's created"""
    if created and instance.status == 'pending':
        # Don't process immediately to avoid blocking the request
        # This will be handled by the event processor
        pass


@receiver(post_save, sender=EventDelivery)
def log_delivery_status_change(sender, instance, **kwargs):
    """Log delivery status changes"""
    if hasattr(instance, '_state') and instance._state.adding:
        # New delivery created
        print(f"New delivery created: {instance.id} for event {instance.event.id}")
    else:
        # Delivery updated
        print(f"Delivery {instance.id} status changed to: {instance.status}")


@receiver(post_delete, sender=Event)
def cleanup_event_deliveries(sender, instance, **kwargs):
    """Clean up related deliveries when event is deleted"""
    # This is handled automatically by CASCADE in the model
    print(f"Event {instance.id} deleted, cleaning up related deliveries")


# Signal to trigger event processing
def trigger_event_processing(event_id):
    """Trigger event processing for a specific event"""
    try:
        event = Event.objects.get(id=event_id)
        event_service = EventService()
        event_service.process_event(event)
    except Event.DoesNotExist:
        print(f"Event {event_id} not found")
    except Exception as e:
        print(f"Error processing event {event_id}: {e}")


# Signal to retry failed deliveries
def retry_failed_deliveries():
    """Retry failed deliveries"""
    try:
        event_service = EventService()
        event_service.retry_failed_deliveries()
    except Exception as e:
        print(f"Error retrying failed deliveries: {e}")


# Signal to cleanup expired events
def cleanup_expired_events():
    """Clean up expired events"""
    try:
        event_service = EventService()
        event_service.cleanup_expired_events()
    except Exception as e:
        print(f"Error cleaning up expired events: {e}")
