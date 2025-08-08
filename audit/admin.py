from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg, Max, Min
from .models import (
    AuditLog, SecurityEvent, PerformanceMetric, DataChangeLog,
    APIAuditLog, DistributedTrace, AuditConfiguration
)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'level', 'log_type', 'service_name', 'user_id', 'action', 'resource_type', 'response_status')
    list_filter = ('level', 'log_type', 'service_name', 'response_status', 'timestamp')
    search_fields = ('message', 'user_id', 'session_id', 'request_id', 'trace_id')
    readonly_fields = ('id', 'timestamp')
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('level', 'log_type', 'service_name', 'message')
        }),
        ('User Context', {
            'fields': ('user_id', 'session_id', 'request_id', 'trace_id', 'span_id')
        }),
        ('Request Details', {
            'fields': ('ip_address', 'user_agent', 'request_method', 'request_path', 'request_params', 'request_headers', 'request_body'),
            'classes': ('collapse',)
        }),
        ('Response Details', {
            'fields': ('response_status', 'response_time_ms', 'response_size', 'response_body'),
            'classes': ('collapse',)
        }),
        ('Action Details', {
            'fields': ('action', 'resource_type', 'resource_id', 'old_values', 'new_values', 'changed_fields'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_type', 'error_message', 'stack_trace'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('details', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('content_type')


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'event_type', 'severity', 'user_id', 'ip_address', 'risk_score', 'is_resolved')
    list_filter = ('event_type', 'severity', 'is_resolved', 'timestamp')
    search_fields = ('description', 'user_id', 'ip_address', 'session_id')
    readonly_fields = ('id', 'timestamp')
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Event Information', {
            'fields': ('event_type', 'severity', 'description')
        }),
        ('User Context', {
            'fields': ('user_id', 'ip_address', 'user_agent', 'session_id')
        }),
        ('Risk Assessment', {
            'fields': ('risk_score', 'risk_factors')
        }),
        ('Response Tracking', {
            'fields': ('is_resolved', 'resolved_at', 'resolved_by', 'resolution_notes')
        }),
        ('Details', {
            'fields': ('details', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_resolved', 'mark_as_unresolved']
    
    def mark_as_resolved(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(is_resolved=True, resolved_at=timezone.now())
        self.message_user(request, f'{updated} security events marked as resolved.')
    mark_as_resolved.short_description = "Mark selected events as resolved"
    
    def mark_as_unresolved(self, request, queryset):
        updated = queryset.update(is_resolved=False, resolved_at=None, resolved_by=None)
        self.message_user(request, f'{updated} security events marked as unresolved.')
    mark_as_unresolved.short_description = "Mark selected events as unresolved"


@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'service_name', 'metric_type', 'metric_name', 'value', 'unit', 'endpoint')
    list_filter = ('metric_type', 'service_name', 'timestamp')
    search_fields = ('metric_name', 'endpoint', 'service_name')
    readonly_fields = ('id', 'timestamp')
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Metric Information', {
            'fields': ('service_name', 'metric_type', 'metric_name', 'value', 'unit')
        }),
        ('Context', {
            'fields': ('endpoint', 'method', 'user_id', 'session_id')
        }),
        ('Additional Data', {
            'fields': ('tags', 'metadata'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DataChangeLog)
class DataChangeLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'service_name', 'change_type', 'model_name', 'user_id', 'ip_address')
    list_filter = ('change_type', 'service_name', 'timestamp')
    search_fields = ('model_name', 'user_id', 'service_name')
    readonly_fields = ('id', 'timestamp')
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Change Information', {
            'fields': ('service_name', 'change_type', 'model_name', 'object_id', 'content_type')
        }),
        ('User Context', {
            'fields': ('user_id', 'session_id', 'ip_address', 'request_id')
        }),
        ('Change Data', {
            'fields': ('old_values', 'new_values', 'changed_fields'),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': ('reason', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('content_type')


@admin.register(APIAuditLog)
class APIAuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'service_name', 'method', 'endpoint', 'response_status', 'response_time_ms', 'user_id')
    list_filter = ('method', 'response_status', 'status_category', 'service_name', 'timestamp')
    search_fields = ('endpoint', 'user_id', 'request_id', 'trace_id')
    readonly_fields = ('id', 'timestamp')
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Request Information', {
            'fields': ('service_name', 'endpoint', 'method', 'response_status', 'status_category')
        }),
        ('User Context', {
            'fields': ('user_id', 'session_id', 'request_id', 'trace_id', 'span_id')
        }),
        ('Request Details', {
            'fields': ('ip_address', 'user_agent', 'referer', 'request_headers', 'request_params', 'request_body', 'request_size'),
            'classes': ('collapse',)
        }),
        ('Response Details', {
            'fields': ('response_time_ms', 'response_size', 'response_body'),
            'classes': ('collapse',)
        }),
        ('Performance', {
            'fields': ('database_queries', 'cache_hits', 'cache_misses'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_type', 'error_message', 'stack_trace'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )


@admin.register(DistributedTrace)
class DistributedTraceAdmin(admin.ModelAdmin):
    list_display = ('trace_id', 'span_id', 'service_name', 'operation_name', 'status', 'duration_ms', 'start_time')
    list_filter = ('status', 'service_name', 'start_time')
    search_fields = ('trace_id', 'span_id', 'operation_name', 'service_name')
    readonly_fields = ('id', 'start_time')
    date_hierarchy = 'start_time'
    
    fieldsets = (
        ('Trace Information', {
            'fields': ('trace_id', 'parent_span_id', 'span_id', 'service_name', 'operation_name')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time', 'duration_ms', 'status')
        }),
        ('Context', {
            'fields': ('user_id', 'session_id', 'request_id')
        }),
        ('Data', {
            'fields': ('tags', 'metadata'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_type', 'error_message', 'stack_trace'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_failed']
    
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='completed', end_time=timezone.now())
        self.message_user(request, f'{updated} traces marked as completed.')
    mark_as_completed.short_description = "Mark selected traces as completed"
    
    def mark_as_failed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='failed', end_time=timezone.now())
        self.message_user(request, f'{updated} traces marked as failed.')
    mark_as_failed.short_description = "Mark selected traces as failed"


@admin.register(AuditConfiguration)
class AuditConfigurationAdmin(admin.ModelAdmin):
    list_display = ('service_name', 'enabled', 'log_level', 'retention_days', 'batch_size')
    list_filter = ('enabled', 'log_level', 'archive_enabled')
    search_fields = ('service_name',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Settings', {
            'fields': ('service_name', 'enabled', 'log_level', 'log_types')
        }),
        ('Retention Settings', {
            'fields': ('retention_days', 'archive_enabled', 'archive_after_days')
        }),
        ('Performance Settings', {
            'fields': ('batch_size', 'flush_interval_seconds')
        }),
        ('Security Settings', {
            'fields': ('mask_sensitive_fields', 'exclude_paths', 'exclude_methods'),
            'classes': ('collapse',)
        }),
        ('Notification Settings', {
            'fields': ('alert_on_errors', 'alert_on_security_events', 'alert_recipients'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# Custom admin actions for bulk operations
class AuditLogAdminWithActions(AuditLogAdmin):
    actions = ['export_logs', 'cleanup_old_logs']
    
    def export_logs(self, request, queryset):
        # TODO: Implement log export functionality
        self.message_user(request, f'{queryset.count()} logs selected for export.')
    export_logs.short_description = "Export selected logs"
    
    def cleanup_old_logs(self, request, queryset):
        # TODO: Implement log cleanup functionality
        self.message_user(request, f'{queryset.count()} old logs selected for cleanup.')
    cleanup_old_logs.short_description = "Cleanup old logs"


class SecurityEventAdminWithActions(SecurityEventAdmin):
    actions = ['export_events', 'bulk_resolve']
    
    def export_events(self, request, queryset):
        # TODO: Implement event export functionality
        self.message_user(request, f'{queryset.count()} events selected for export.')
    export_events.short_description = "Export selected events"
    
    def bulk_resolve(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(is_resolved=True, resolved_at=timezone.now())
        self.message_user(request, f'{updated} events resolved in bulk.')
    bulk_resolve.short_description = "Resolve selected events in bulk"


# Re-register models with actions
admin.site.unregister(AuditLog)
admin.site.register(AuditLog, AuditLogAdminWithActions)

admin.site.unregister(SecurityEvent)
admin.site.register(SecurityEvent, SecurityEventAdminWithActions)
