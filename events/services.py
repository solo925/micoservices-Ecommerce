import uuid
import json
import requests
import redis
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from .models import Event, EventSubscription, EventDelivery


class EventService:
    """Service for managing event-driven communication"""
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    
    def publish_event(self, event_type, source_service, data=None, metadata=None, 
                     target_service=None, correlation_id=None, causation_id=None,
                     priority=0, scheduled_at=None, expires_at=None):
        """Publish an event to the event bus"""
        
        # Create event record
        event = Event.objects.create(
            event_type=event_type,
            source_service=source_service,
            target_service=target_service or '',
            correlation_id=correlation_id,
            causation_id=causation_id,
            data=data or {},
            metadata=metadata or {},
            priority=priority,
            scheduled_at=scheduled_at,
            expires_at=expires_at
        )
        
        # Publish to Redis for immediate processing
        if not scheduled_at or scheduled_at <= timezone.now():
            self._publish_to_redis(event)
        
        return event
    
    def _publish_to_redis(self, event):
        """Publish event to Redis queue"""
        event_data = {
            'event_id': str(event.id),
            'event_type': event.event_type,
            'source_service': event.source_service,
            'target_service': event.target_service,
            'correlation_id': str(event.correlation_id) if event.correlation_id else None,
            'causation_id': str(event.causation_id) if event.causation_id else None,
            'data': event.data,
            'metadata': event.metadata,
            'priority': event.priority,
            'created_at': event.created_at.isoformat(),
        }
        
        # Publish to Redis channel
        self.redis_client.publish('events', json.dumps(event_data, cls=DjangoJSONEncoder))
        
        # Also add to priority queue for processing
        queue_name = f"events:priority:{event.priority}"
        self.redis_client.lpush(queue_name, json.dumps(event_data, cls=DjangoJSONEncoder))
    
    def get_pending_events(self, service_name=None, event_type=None, limit=100):
        """Get pending events for processing"""
        queryset = Event.objects.filter(status='pending')
        
        if service_name:
            queryset = queryset.filter(target_service=service_name)
        
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        return queryset.order_by('-priority', 'created_at')[:limit]
    
    def process_event(self, event):
        """Process a single event"""
        try:
            event.mark_processing()
            
            # Find subscriptions for this event
            subscriptions = EventSubscription.objects.filter(
                event_type=event.event_type,
                is_active=True
            )
            
            if event.source_service:
                subscriptions = subscriptions.filter(
                    source_service__in=['', event.source_service]
                )
            
            # Create delivery records
            deliveries = []
            for subscription in subscriptions:
                delivery = EventDelivery.objects.create(
                    event=event,
                    subscription=subscription
                )
                deliveries.append(delivery)
            
            # Process deliveries
            for delivery in deliveries:
                self._process_delivery(delivery)
            
            # Mark event as completed if all deliveries succeeded
            if all(d.status in ['delivered', 'failed'] for d in deliveries):
                if any(d.status == 'delivered' for d in deliveries):
                    event.mark_completed()
                else:
                    event.mark_failed("All deliveries failed")
            
        except Exception as e:
            event.mark_failed(str(e))
            raise
    
    def _process_delivery(self, delivery):
        """Process a single delivery"""
        try:
            # Prepare request
            headers = {
                'Content-Type': 'application/json',
                'X-Event-Type': delivery.event.event_type,
                'X-Source-Service': delivery.event.source_service,
                'X-Event-ID': str(delivery.event.id),
            }
            
            # Add authentication
            if delivery.subscription.auth_type == 'bearer':
                headers['Authorization'] = f"Bearer {delivery.subscription.auth_credentials.get('token', '')}"
            elif delivery.subscription.auth_type == 'api_key':
                headers['X-API-Key'] = delivery.subscription.auth_credentials.get('api_key', '')
            
            # Prepare payload
            payload = {
                'event_id': str(delivery.event.id),
                'event_type': delivery.event.event_type,
                'source_service': delivery.event.source_service,
                'correlation_id': str(delivery.event.correlation_id) if delivery.event.correlation_id else None,
                'causation_id': str(delivery.event.causation_id) if delivery.event.causation_id else None,
                'data': delivery.event.data,
                'metadata': delivery.event.metadata,
                'timestamp': delivery.event.created_at.isoformat(),
            }
            
            # Send request
            delivery.mark_sent()
            response = requests.post(
                delivery.subscription.endpoint_url,
                json=payload,
                headers=headers,
                timeout=delivery.subscription.timeout_seconds
            )
            
            if response.status_code in [200, 201, 202]:
                delivery.mark_delivered(response.status_code, response.text)
            else:
                delivery.mark_failed(f"HTTP {response.status_code}", response.status_code)
                
        except requests.RequestException as e:
            delivery.mark_failed(str(e))
        except Exception as e:
            delivery.mark_failed(str(e))
    
    def retry_failed_deliveries(self, max_retries=3):
        """Retry failed deliveries"""
        failed_deliveries = EventDelivery.objects.filter(
            status='failed',
            attempt_count__lt=max_retries
        )
        
        for delivery in failed_deliveries:
            delivery.increment_attempt()
            if delivery.status == 'retry':
                self._process_delivery(delivery)
    
    def cleanup_expired_events(self):
        """Clean up expired events"""
        expired_events = Event.objects.filter(
            expires_at__lt=timezone.now(),
            status__in=['pending', 'processing']
        )
        
        for event in expired_events:
            event.mark_failed("Event expired")
    
    def get_event_stats(self, days=30):
        """Get event statistics"""
        since = timezone.now() - timedelta(days=days)
        
        stats = {
            'total_events': Event.objects.filter(created_at__gte=since).count(),
            'events_by_type': {},
            'events_by_status': {},
            'events_by_service': {},
            'delivery_stats': {
                'total_deliveries': EventDelivery.objects.filter(created_at__gte=since).count(),
                'successful_deliveries': EventDelivery.objects.filter(
                    created_at__gte=since, status='delivered'
                ).count(),
                'failed_deliveries': EventDelivery.objects.filter(
                    created_at__gte=since, status='failed'
                ).count(),
            }
        }
        
        # Events by type
        for event_type, _ in Event.EVENT_TYPES:
            count = Event.objects.filter(
                event_type=event_type, created_at__gte=since
            ).count()
            if count > 0:
                stats['events_by_type'][event_type] = count
        
        # Events by status
        for status, _ in Event.STATUS_CHOICES:
            count = Event.objects.filter(
                status=status, created_at__gte=since
            ).count()
            if count > 0:
                stats['events_by_status'][status] = count
        
        # Events by service
        services = Event.objects.filter(created_at__gte=since).values_list(
            'source_service', flat=True
        ).distinct()
        
        for service in services:
            count = Event.objects.filter(
                source_service=service, created_at__gte=since
            ).count()
            stats['events_by_service'][service] = count
        
        return stats


class EventSubscriptionService:
    """Service for managing event subscriptions"""
    
    def create_subscription(self, subscriber_service, event_type, endpoint_url,
                          source_service=None, auth_type='none', auth_credentials=None,
                          retry_count=3, timeout_seconds=30, rate_limits=None):
        """Create a new event subscription"""
        
        subscription = EventSubscription.objects.create(
            subscriber_service=subscriber_service,
            event_type=event_type,
            source_service=source_service or '',
            endpoint_url=endpoint_url,
            auth_type=auth_type,
            auth_credentials=auth_credentials or {},
            retry_count=retry_count,
            timeout_seconds=timeout_seconds,
            rate_limit_per_minute=rate_limits.get('per_minute', 60) if rate_limits else 60,
            rate_limit_per_hour=rate_limits.get('per_hour', 1000) if rate_limits else 1000,
        )
        
        return subscription
    
    def get_subscriptions_for_service(self, service_name):
        """Get all subscriptions for a service"""
        return EventSubscription.objects.filter(
            subscriber_service=service_name,
            is_active=True
        )
    
    def get_subscriptions_for_event_type(self, event_type, source_service=None):
        """Get subscriptions for a specific event type"""
        queryset = EventSubscription.objects.filter(
            event_type=event_type,
            is_active=True
        )
        
        if source_service:
            queryset = queryset.filter(
                source_service__in=['', source_service]
            )
        
        return queryset
    
    def deactivate_subscription(self, subscription_id):
        """Deactivate a subscription"""
        try:
            subscription = EventSubscription.objects.get(id=subscription_id)
            subscription.is_active = False
            subscription.save(update_fields=['is_active'])
            return True
        except EventSubscription.DoesNotExist:
            return False
    
    def update_subscription(self, subscription_id, **kwargs):
        """Update a subscription"""
        try:
            subscription = EventSubscription.objects.get(id=subscription_id)
            for field, value in kwargs.items():
                if hasattr(subscription, field):
                    setattr(subscription, field, value)
            subscription.save()
            return subscription
        except EventSubscription.DoesNotExist:
            return None
