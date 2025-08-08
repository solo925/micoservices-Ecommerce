from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum
from .models import (
    NotificationTemplate, NotificationChannel, Notification, NotificationDelivery,
    NotificationPreference, NotificationLog, NotificationBatch
)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'is_active', 'created_at', 'updated_at')
    list_filter = ('template_type', 'is_active', 'created_at')
    search_fields = ('name', 'subject', 'content')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'template_type', 'is_active')
        }),
        ('Content', {
            'fields': ('subject', 'content', 'html_content')
        }),
        ('Variables', {
            'fields': ('variables',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'channel_type', 'is_active', 'rate_limit_display', 'created_at')
    list_filter = ('channel_type', 'is_active', 'created_at')
    search_fields = ('name', 'channel_type')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'channel_type', 'is_active')
        }),
        ('Email Configuration', {
            'fields': ('smtp_host', 'smtp_port', 'smtp_username', 'smtp_password', 'smtp_use_tls'),
            'classes': ('collapse',)
        }),
        ('SMS Configuration', {
            'fields': ('sms_provider', 'sms_api_key', 'sms_api_secret', 'sms_from_number'),
            'classes': ('collapse',)
        }),
        ('Webhook Configuration', {
            'fields': ('webhook_url', 'webhook_headers', 'webhook_method'),
            'classes': ('collapse',)
        }),
        ('Rate Limiting', {
            'fields': ('rate_limit_per_hour', 'rate_limit_per_day')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def rate_limit_display(self, obj):
        return f"{obj.rate_limit_per_hour}/hour, {obj.rate_limit_per_day}/day"
    rate_limit_display.short_description = 'Rate Limits'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('notification_type', 'recipient_display', 'channel', 'priority', 'status_display', 'created_at')
    list_filter = ('notification_type', 'channel', 'priority', 'is_sent', 'delivery_status', 'created_at')
    search_fields = ('recipient_email', 'recipient_phone', 'subject', 'content')
    readonly_fields = ('id', 'created_at', 'updated_at', 'sent_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('notification_type', 'template', 'channel', 'priority')
        }),
        ('Recipient', {
            'fields': ('recipient_email', 'recipient_phone', 'recipient_user_id')
        }),
        ('Content', {
            'fields': ('subject', 'content', 'html_content')
        }),
        ('Status', {
            'fields': ('is_sent', 'delivery_status', 'error_message', 'retry_count', 'max_retries')
        }),
        ('Scheduling', {
            'fields': ('scheduled_at', 'expires_at')
        }),
        ('Metadata', {
            'fields': ('metadata', 'context_data'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'sent_at'),
            'classes': ('collapse',)
        }),
    )
    
    def recipient_display(self, obj):
        if obj.recipient_email:
            return obj.recipient_email
        elif obj.recipient_phone:
            return obj.recipient_phone
        elif obj.recipient_user_id:
            return f"User {obj.recipient_user_id}"
        return "N/A"
    recipient_display.short_description = 'Recipient'
    
    def status_display(self, obj):
        if obj.is_sent:
            return format_html('<span style="color: green;">✓ Sent</span>')
        elif obj.delivery_status == 'failed':
            return format_html('<span style="color: red;">✗ Failed</span>')
        elif obj.delivery_status == 'pending':
            return format_html('<span style="color: orange;">⏳ Pending</span>')
        return obj.delivery_status
    status_display.short_description = 'Status'


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ('notification', 'attempt_number', 'status', 'sent_at', 'delivered_at')
    list_filter = ('status', 'attempt_number', 'sent_at', 'delivered_at')
    search_fields = ('notification__recipient_email', 'notification__recipient_phone', 'provider_message_id')
    readonly_fields = ('id', 'created_at')
    
    fieldsets = (
        ('Delivery Information', {
            'fields': ('notification', 'attempt_number', 'status')
        }),
        ('Provider Response', {
            'fields': ('provider_message_id', 'provider_response', 'error_message', 'error_code'),
            'classes': ('collapse',)
        }),
        ('Timing', {
            'fields': ('sent_at', 'delivered_at', 'created_at')
        }),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'email_enabled', 'sms_enabled', 'push_enabled', 'digest_frequency', 'updated_at')
    list_filter = ('email_enabled', 'sms_enabled', 'push_enabled', 'digest_frequency', 'created_at')
    search_fields = ('user_id',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user_id',)
        }),
        ('Email Preferences', {
            'fields': ('email_enabled', 'email_order_updates', 'email_payment_updates', 'email_promotions', 'email_newsletter')
        }),
        ('SMS Preferences', {
            'fields': ('sms_enabled', 'sms_order_updates', 'sms_payment_updates', 'sms_promotions')
        }),
        ('Push Preferences', {
            'fields': ('push_enabled', 'push_order_updates', 'push_payment_updates', 'push_promotions')
        }),
        ('Frequency', {
            'fields': ('digest_frequency',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('level', 'message_short', 'notification', 'channel', 'user_id', 'created_at')
    list_filter = ('level', 'notification', 'channel', 'user_id', 'created_at')
    search_fields = ('message', 'notification__recipient_email')
    readonly_fields = ('id', 'created_at')
    
    fieldsets = (
        ('Log Information', {
            'fields': ('level', 'message', 'notification', 'channel', 'user_id')
        }),
        ('Context', {
            'fields': ('context_data',),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def message_short(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_short.short_description = 'Message'


@admin.register(NotificationBatch)
class NotificationBatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'template', 'channel', 'status', 'progress_display', 'created_at')
    list_filter = ('status', 'template', 'channel', 'created_at')
    search_fields = ('name', 'template__name', 'channel__name')
    readonly_fields = ('id', 'created_at', 'updated_at', 'started_at', 'completed_at', 'progress_percentage')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'template', 'channel', 'status')
        }),
        ('Batch Configuration', {
            'fields': ('total_recipients', 'sent_count', 'failed_count', 'batch_size', 'delay_between_batches')
        }),
        ('Scheduling', {
            'fields': ('scheduled_at', 'started_at', 'completed_at')
        }),
        ('Progress', {
            'fields': ('progress_percentage',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def progress_display(self, obj):
        if obj.status == 'completed':
            return f"{obj.sent_count}/{obj.total_recipients} sent"
        elif obj.status == 'processing':
            return f"{obj.sent_count + obj.failed_count}/{obj.total_recipients} processed"
        return f"{obj.sent_count + obj.failed_count}/{obj.total_recipients}"
    progress_display.short_description = 'Progress'


# Custom admin actions
@admin.register(Notification)
class NotificationAdminWithActions(NotificationAdmin):
    actions = ['retry_failed_notifications', 'mark_as_sent', 'mark_as_failed']
    
    def retry_failed_notifications(self, request, queryset):
        from .services import NotificationDeliveryService
        
        retried_count = 0
        for notification in queryset.filter(delivery_status='failed'):
            if notification.can_retry:
                success, error = NotificationDeliveryService.send_notification(notification)
                if success:
                    retried_count += 1
        
        self.message_user(request, f'{retried_count} notifications retried successfully.')
    retry_failed_notifications.short_description = "Retry failed notifications"
    
    def mark_as_sent(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(is_sent=True, sent_at=timezone.now(), delivery_status='sent')
        self.message_user(request, f'{updated} notifications marked as sent.')
    mark_as_sent.short_description = "Mark selected notifications as sent"
    
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(delivery_status='failed')
        self.message_user(request, f'{updated} notifications marked as failed.')
    mark_as_failed.short_description = "Mark selected notifications as failed"


@admin.register(NotificationBatch)
class NotificationBatchAdminWithActions(NotificationBatchAdmin):
    actions = ['process_batches', 'cancel_batches']
    
    def process_batches(self, request, queryset):
        from .services import NotificationBatchService
        
        processed_count = 0
        for batch in queryset.filter(status='pending'):
            try:
                NotificationBatchService.process_batch(batch.id)
                processed_count += 1
            except Exception as e:
                self.message_user(request, f'Error processing batch {batch.id}: {str(e)}', level='ERROR')
        
        self.message_user(request, f'{processed_count} batches processed successfully.')
    process_batches.short_description = "Process selected batches"
    
    def cancel_batches(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status='pending').update(status='failed')
        self.message_user(request, f'{updated} batches cancelled.')
    cancel_batches.short_description = "Cancel selected batches"


# Re-register models with actions
admin.site.unregister(Notification)
admin.site.register(Notification, NotificationAdminWithActions)

admin.site.unregister(NotificationBatch)
admin.site.register(NotificationBatch, NotificationBatchAdminWithActions)
