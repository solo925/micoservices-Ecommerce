from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import Event, EventSubscription, EventDelivery


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'event_type', 'source_service', 'target_service', 
        'status', 'priority', 'created_at', 'processed_at'
    ]
    list_filter = [
        'event_type', 'source_service', 'target_service', 'status', 
        'priority', 'created_at'
    ]
    search_fields = [
        'event_type', 'source_service', 'target_service', 
        'correlation_id', 'causation_id'
    ]
    readonly_fields = [
        'id', 'created_at', 'processed_at', 'retry_count', 
        'error_message', 'error_details'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'event_type', 'source_service', 'target_service')
        }),
        ('Event Data', {
            'fields': ('correlation_id', 'causation_id', 'data', 'metadata')
        }),
        ('Status & Timing', {
            'fields': ('status', 'priority', 'retry_count', 'max_retries', 
                      'created_at', 'processed_at', 'scheduled_at', 'expires_at')
        }),
        ('Error Information', {
            'fields': ('error_message', 'error_details'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_failed', 'retry_failed_events']
    
    def mark_as_completed(self, request, queryset):
        """Mark selected events as completed"""
        updated = queryset.update(
            status='completed',
            processed_at=timezone.now()
        )
        self.message_user(request, f'{updated} events marked as completed.')
    mark_as_completed.short_description = "Mark selected events as completed"
    
    def mark_as_failed(self, request, queryset):
        """Mark selected events as failed"""
        updated = queryset.update(status='failed')
        self.message_user(request, f'{updated} events marked as failed.')
    mark_as_failed.short_description = "Mark selected events as failed"
    
    def retry_failed_events(self, request, queryset):
        """Retry failed events"""
        failed_events = queryset.filter(status='failed')
        retried_count = 0
        
        for event in failed_events:
            if event.can_retry:
                event.increment_retry()
                retried_count += 1
        
        self.message_user(request, f'{retried_count} events retried.')
    retry_failed_events.short_description = "Retry failed events"


@admin.register(EventSubscription)
class EventSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'subscriber_service', 'event_type', 'source_service',
        'endpoint_url', 'is_active', 'created_at'
    ]
    list_filter = [
        'subscriber_service', 'event_type', 'source_service', 
        'is_active', 'auth_type', 'created_at'
    ]
    search_fields = [
        'subscriber_service', 'event_type', 'source_service', 
        'endpoint_url'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'subscriber_service', 'event_type', 'source_service')
        }),
        ('Endpoint Configuration', {
            'fields': ('endpoint_url', 'is_active', 'retry_count', 'timeout_seconds')
        }),
        ('Authentication', {
            'fields': ('auth_type', 'auth_credentials'),
            'classes': ('collapse',)
        }),
        ('Rate Limiting', {
            'fields': ('rate_limit_per_minute', 'rate_limit_per_hour'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_subscriptions', 'deactivate_subscriptions']
    
    def activate_subscriptions(self, request, queryset):
        """Activate selected subscriptions"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} subscriptions activated.')
    activate_subscriptions.short_description = "Activate selected subscriptions"
    
    def deactivate_subscriptions(self, request, queryset):
        """Deactivate selected subscriptions"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} subscriptions deactivated.')
    deactivate_subscriptions.short_description = "Deactivate selected subscriptions"


@admin.register(EventDelivery)
class EventDeliveryAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'event_type', 'subscriber_service', 'status', 
        'attempt_count', 'sent_at', 'delivered_at'
    ]
    list_filter = [
        'status', 'attempt_count', 'sent_at', 'delivered_at',
        'event__event_type', 'subscription__subscriber_service'
    ]
    search_fields = [
        'event__event_type', 'subscription__subscriber_service',
        'subscription__endpoint_url'
    ]
    readonly_fields = [
        'id', 'event', 'subscription', 'sent_at', 'delivered_at',
        'response_status', 'response_body', 'error_message',
        'created_at', 'updated_at'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'event', 'subscription')
        }),
        ('Status & Attempts', {
            'fields': ('status', 'attempt_count', 'max_attempts')
        }),
        ('Timing', {
            'fields': ('sent_at', 'delivered_at', 'created_at', 'updated_at')
        }),
        ('Response Details', {
            'fields': ('response_status', 'response_body', 'error_message'),
            'classes': ('collapse',)
        }),
    )
    
    def event_type(self, obj):
        """Get event type from related event"""
        return obj.event.event_type if obj.event else '-'
    event_type.short_description = 'Event Type'
    
    def subscriber_service(self, obj):
        """Get subscriber service from related subscription"""
        return obj.subscription.subscriber_service if obj.subscription else '-'
    subscriber_service.short_description = 'Subscriber Service'
    
    actions = ['retry_failed_deliveries', 'mark_as_delivered']
    
    def retry_failed_deliveries(self, request, queryset):
        """Retry failed deliveries"""
        failed_deliveries = queryset.filter(status='failed')
        retried_count = 0
        
        for delivery in failed_deliveries:
            if delivery.attempt_count < delivery.max_attempts:
                delivery.increment_attempt()
                retried_count += 1
        
        self.message_user(request, f'{retried_count} deliveries retried.')
    retry_failed_deliveries.short_description = "Retry failed deliveries"
    
    def mark_as_delivered(self, request, queryset):
        """Mark selected deliveries as delivered"""
        updated = queryset.update(
            status='delivered',
            delivered_at=timezone.now()
        )
        self.message_user(request, f'{updated} deliveries marked as delivered.')
    mark_as_delivered.short_description = "Mark selected deliveries as delivered"
