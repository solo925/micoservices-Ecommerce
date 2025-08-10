import uuid
import json
import requests
import redis
from datetime import timedelta
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q, Count, Avg, F, Sum, Case, When, Value, IntegerField
from django.core.cache import cache
from .models import Event, EventSubscription, EventDelivery


class EventService:
    """Service for managing event-driven communication with optimized operations."""
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        # Class-level cache for event statistics
        self._stats_cache = {}
        self._cache_ttl = 300  # 5 minutes
    
    def publish_event(self, event_type, source_service, data=None, metadata=None, 
                     target_service=None, correlation_id=None, causation_id=None,
                     priority=0, scheduled_at=None, expires_at=None):
        """Publish an event to the event bus with optimized creation."""
        
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
        
        # Clear stats cache
        self._clear_stats_cache()
        
        return event
    
    def bulk_publish_events(self, events_data: List[Dict[str, Any]]) -> List[Event]:
        """Bulk publish multiple events for better performance."""
        if not events_data:
            return []
        
        events = []
        for event_data in events_data:
            event = Event(
                event_type=event_data['event_type'],
                source_service=event_data['source_service'],
                target_service=event_data.get('target_service', ''),
                correlation_id=event_data.get('correlation_id'),
                causation_id=event_data.get('causation_id'),
                data=event_data.get('data', {}),
                metadata=event_data.get('metadata', {}),
                priority=event_data.get('priority', 0),
                scheduled_at=event_data.get('scheduled_at'),
                expires_at=event_data.get('expires_at')
            )
            events.append(event)
        
        # Bulk create events
        created_events = Event.objects.bulk_create(events)
        
        # Publish to Redis and clear cache
        for event in created_events:
            if not event.scheduled_at or event.scheduled_at <= timezone.now():
                self._publish_to_redis(event)
        
        self._clear_stats_cache()
        return created_events
    
    def _publish_to_redis(self, event):
        """Publish event to Redis queue with optimized serialization."""
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
        """Get pending events for processing with optimized querying."""
        queryset = Event.objects.select_related().filter(status='pending')
        
        if service_name:
            queryset = queryset.filter(target_service=service_name)
        
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        return list(queryset.order_by('-priority', 'created_at')[:limit])
    
    def process_event(self, event):
        """Process a single event with optimized subscription handling."""
        try:
            event.mark_processing()
            
            # Find subscriptions for this event with optimized query
            subscriptions = EventSubscription.objects.select_related().filter(
                event_type=event.event_type,
                is_active=True
            )
            
            if event.source_service:
                subscriptions = subscriptions.filter(
                    source_service__in=['', event.source_service]
                )
            
            # Create delivery records in bulk
            deliveries = [
                EventDelivery(
                    event=event,
                    subscription=subscription
                )
                for subscription in subscriptions
            ]
            
            if deliveries:
                EventDelivery.objects.bulk_create(deliveries)
                
                # Process deliveries
                for delivery in deliveries:
                    self._process_delivery(delivery)
                
                # Check delivery status and update event
                delivered_count = sum(1 for d in deliveries if d.status == 'delivered')
                failed_count = sum(1 for d in deliveries if d.status == 'failed')
                
                if delivered_count > 0:
                    event.mark_completed()
                elif failed_count == len(deliveries):
                    event.mark_failed("All deliveries failed")
            
        except Exception as e:
            event.mark_failed(str(e))
            raise
    
    def _process_delivery(self, delivery):
        """Process a single delivery with optimized error handling."""
        try:
            # Prepare request headers and payload
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
                headers['X-API-Key'] = delivery.subscription.auth_credentials.get('api_key', '')"
            
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
        """Retry failed deliveries with bulk operations."""
        failed_deliveries = EventDelivery.objects.select_related('event', 'subscription').filter(
            status='failed',
            attempt_count__lt=max_retries
        )
        
        # Prepare deliveries for retry
        deliveries_to_retry = []
        for delivery in failed_deliveries:
            delivery.increment_attempt()
            if delivery.status == 'retry':
                deliveries_to_retry.append(delivery)
        
        # Bulk update attempt counts
        if deliveries_to_retry:
            EventDelivery.objects.bulk_update(
                deliveries_to_retry,
                ['attempt_count', 'status', 'last_attempt_at']
            )
            
            # Process retries
            for delivery in deliveries_to_retry:
                self._process_delivery(delivery)
    
    def cleanup_expired_events(self):
        """Clean up expired events with bulk operations."""
        expired_events = Event.objects.filter(
            expires_at__lt=timezone.now(),
            status__in=['pending', 'processing']
        )
        
        if expired_events:
            # Bulk update expired events
            expired_events.update(
                status='failed',
                error_message='Event expired',
                updated_at=timezone.now()
            )
    
    def get_event_stats(self, days=30):
        """Get event statistics with optimized queries and caching."""
        cache_key = f"event_stats_{days}"
        
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]
        
        since = timezone.now() - timedelta(days=days)
        
        # Use aggregate for efficient statistics calculation
        base_events = Event.objects.filter(created_at__gte=since)
        base_deliveries = EventDelivery.objects.filter(created_at__gte=since)
        
        # Get basic counts
        total_events = base_events.count()
        total_deliveries = base_deliveries.count()
        
        # Get delivery statistics using aggregate
        delivery_stats = base_deliveries.aggregate(
            successful_deliveries=Count('id', filter=Q(status='delivered')),
            failed_deliveries=Count('id', filter=Q(status='failed')),
            pending_deliveries=Count('id', filter=Q(status='pending'))
        )
        
        # Get events by type using values and annotate
        events_by_type = base_events.values('event_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Get events by status using values and annotate
        events_by_status = base_events.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Get events by service using values and annotate
        events_by_service = base_events.values('source_service').annotate(
            count=Count('id')
        ).order_by('-count')
        
        stats = {
            'total_events': total_events,
            'events_by_type': {item['event_type']: item['count'] for item in events_by_type},
            'events_by_status': {item['status']: item['count'] for item in events_by_status},
            'events_by_service': {item['source_service']: item['count'] for item in events_by_service},
            'delivery_stats': {
                'total_deliveries': total_deliveries,
                'successful_deliveries': delivery_stats['successful_deliveries'],
                'failed_deliveries': delivery_stats['failed_deliveries'],
                'pending_deliveries': delivery_stats['pending_deliveries'],
            }
        }
        
        # Cache the result
        self._stats_cache[cache_key] = stats
        
        # Clear old cache entries
        if len(self._stats_cache) > 20:
            self._stats_cache.clear()
        
        return stats
    
    def _clear_stats_cache(self):
        """Clear statistics cache."""
        self._stats_cache.clear()


class EventSubscriptionService:
    """Service for managing event subscriptions with optimized operations."""
    
    def create_subscription(self, subscriber_service, event_type, endpoint_url,
                          source_service=None, auth_type='none', auth_credentials=None,
                          retry_count=3, timeout_seconds=30, rate_limits=None):
        """Create a new event subscription."""
        
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
    
    def bulk_create_subscriptions(self, subscriptions_data: List[Dict[str, Any]]) -> List[EventSubscription]:
        """Bulk create multiple subscriptions for better performance."""
        if not subscriptions_data:
            return []
        
        subscriptions = []
        for data in subscriptions_data:
            subscription = EventSubscription(
                subscriber_service=data['subscriber_service'],
                event_type=data['event_type'],
                source_service=data.get('source_service', ''),
                endpoint_url=data['endpoint_url'],
                auth_type=data.get('auth_type', 'none'),
                auth_credentials=data.get('auth_credentials', {}),
                retry_count=data.get('retry_count', 3),
                timeout_seconds=data.get('timeout_seconds', 30),
                rate_limit_per_minute=data.get('rate_limits', {}).get('per_minute', 60),
                rate_limit_per_hour=data.get('rate_limits', {}).get('per_hour', 1000),
            )
            subscriptions.append(subscription)
        
        return EventSubscription.objects.bulk_create(subscriptions)
    
    def get_subscriptions_for_service(self, service_name):
        """Get all subscriptions for a service with optimized querying."""
        return list(EventSubscription.objects.select_related().filter(
            subscriber_service=service_name,
            is_active=True
        ))
    
    def get_subscriptions_for_event_type(self, event_type, source_service=None):
        """Get subscriptions for a specific event type with optimized querying."""
        queryset = EventSubscription.objects.select_related().filter(
            event_type=event_type,
            is_active=True
        )
        
        if source_service:
            queryset = queryset.filter(
                source_service__in=['', source_service]
            )
        
        return list(queryset)
    
    def deactivate_subscription(self, subscription_id):
        """Deactivate a subscription with optimized update."""
        try:
            updated_count = EventSubscription.objects.filter(
                id=subscription_id
            ).update(is_active=False)
            return updated_count > 0
        except Exception:
            return False
    
    def bulk_deactivate_subscriptions(self, subscription_ids: List[int]) -> int:
        """Bulk deactivate multiple subscriptions."""
        if not subscription_ids:
            return 0
        
        updated_count = EventSubscription.objects.filter(
            id__in=subscription_ids
        ).update(is_active=False)
        
        return updated_count
    
    def update_subscription(self, subscription_id, **kwargs):
        """Update a subscription with optimized field updates."""
        try:
            subscription = EventSubscription.objects.get(id=subscription_id)
            
            # Track which fields are being updated
            update_fields = []
            for field, value in kwargs.items():
                if hasattr(subscription, field):
                    setattr(subscription, field, value)
                    update_fields.append(field)
            
            if update_fields:
                subscription.save(update_fields=update_fields)
            
            return subscription
        except EventSubscription.DoesNotExist:
            return None
    
    def bulk_update_subscriptions(self, updates: List[Dict[str, Any]]) -> int:
        """Bulk update multiple subscriptions."""
        if not updates:
            return 0
        
        updated_count = 0
        for update_data in updates:
            subscription_id = update_data.pop('id', None)
            if subscription_id:
                subscription = self.update_subscription(subscription_id, **update_data)
                if subscription:
                    updated_count += 1
        
        return updated_count
