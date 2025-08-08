from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Avg
from .models import (
    ServiceRegistry, ServiceInstance, HealthCheck, Configuration,
    ConfigurationHistory, ServiceDependency, ServiceMetrics
)


@admin.register(ServiceRegistry)
class ServiceRegistryAdmin(admin.ModelAdmin):
    list_display = [
        'service_name', 'service_type', 'version', 'status', 'environment',
        'instances_count', 'healthy_instances_count', 'last_heartbeat', 'created_at'
    ]
    list_filter = ['service_type', 'status', 'environment', 'is_public', 'is_secure']
    search_fields = ['service_name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_heartbeat']
    fieldsets = (
        ('Basic Information', {
            'fields': ('service_name', 'service_type', 'version', 'description')
        }),
        ('Endpoints', {
            'fields': ('base_url', 'health_check_url', 'api_docs_url')
        }),
        ('Status & Visibility', {
            'fields': ('status', 'is_public', 'is_secure', 'environment')
        }),
        ('Capabilities & Dependencies', {
            'fields': ('capabilities', 'dependencies', 'config')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_heartbeat'),
            'classes': ('collapse',)
        }),
    )
    actions = ['activate_services', 'deactivate_services', 'put_in_maintenance']
    
    def instances_count(self, obj):
        return obj.instances.count()
    instances_count.short_description = 'Instances'
    
    def healthy_instances_count(self, obj):
        return obj.instances.filter(status='healthy').count()
    healthy_instances_count.short_description = 'Healthy'
    
    def activate_services(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} services activated successfully.')
    activate_services.short_description = 'Activate selected services'
    
    def deactivate_services(self, request, queryset):
        updated = queryset.update(status='inactive')
        self.message_user(request, f'{updated} services deactivated successfully.')
    deactivate_services.short_description = 'Deactivate selected services'
    
    def put_in_maintenance(self, request, queryset):
        updated = queryset.update(status='maintenance')
        self.message_user(request, f'{updated} services put in maintenance mode.')
    put_in_maintenance.short_description = 'Put selected services in maintenance'


@admin.register(ServiceInstance)
class ServiceInstanceAdmin(admin.ModelAdmin):
    list_display = [
        'instance_id', 'service_name', 'host', 'port', 'status', 'is_primary',
        'last_health_check', 'last_heartbeat', 'created_at'
    ]
    list_filter = ['status', 'is_primary', 'protocol', 'service__service_type']
    search_fields = ['instance_id', 'host', 'service__service_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_heartbeat']
    fieldsets = (
        ('Instance Information', {
            'fields': ('service', 'instance_id', 'host', 'port', 'protocol')
        }),
        ('Status & Health', {
            'fields': ('status', 'is_primary', 'last_health_check', 'health_check_interval', 'health_check_timeout')
        }),
        ('Load Balancing', {
            'fields': ('load_balancer_weight', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_heartbeat'),
            'classes': ('collapse',)
        }),
    )
    actions = ['mark_healthy', 'mark_unhealthy', 'mark_maintenance']
    
    def service_name(self, obj):
        return obj.service.service_name
    service_name.short_description = 'Service'
    
    def mark_healthy(self, request, queryset):
        updated = queryset.update(status='healthy')
        self.message_user(request, f'{updated} instances marked as healthy.')
    mark_healthy.short_description = 'Mark selected instances as healthy'
    
    def mark_unhealthy(self, request, queryset):
        updated = queryset.update(status='unhealthy')
        self.message_user(request, f'{updated} instances marked as unhealthy.')
    mark_unhealthy.short_description = 'Mark selected instances as unhealthy'
    
    def mark_maintenance(self, request, queryset):
        updated = queryset.update(status='maintenance')
        self.message_user(request, f'{updated} instances put in maintenance mode.')
    mark_maintenance.short_description = 'Put selected instances in maintenance'


@admin.register(HealthCheck)
class HealthCheckAdmin(admin.ModelAdmin):
    list_display = [
        'service_name', 'instance_id', 'status', 'response_time_ms',
        'response_code', 'checked_at'
    ]
    list_filter = ['status', 'response_code', 'checked_at']
    search_fields = ['service_instance__service__service_name', 'service_instance__instance_id']
    readonly_fields = ['id', 'checked_at']
    fieldsets = (
        ('Health Check Information', {
            'fields': ('service_instance', 'status', 'response_time_ms', 'response_code')
        }),
        ('Error Details', {
            'fields': ('error_message', 'response_body'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('checked_at',),
            'classes': ('collapse',)
        }),
    )
    actions = ['delete_old_health_checks']
    
    def service_name(self, obj):
        return obj.service_instance.service.service_name
    service_name.short_description = 'Service'
    
    def instance_id(self, obj):
        return obj.service_instance.instance_id
    instance_id.short_description = 'Instance'
    
    def delete_old_health_checks(self, request, queryset):
        # Delete health checks older than 30 days
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=30)
        old_checks = HealthCheck.objects.filter(checked_at__lt=cutoff_date)
        count = old_checks.count()
        old_checks.delete()
        self.message_user(request, f'{count} old health checks deleted.')
    delete_old_health_checks.short_description = 'Delete health checks older than 30 days'


@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    list_display = [
        'key', 'config_type', 'service_name', 'environment', 'is_sensitive',
        'is_encrypted', 'version', 'updated_at'
    ]
    list_filter = ['config_type', 'environment', 'is_sensitive', 'is_encrypted', 'updated_at']
    search_fields = ['key', 'description', 'service_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'version', 'previous_value']
    fieldsets = (
        ('Configuration Information', {
            'fields': ('key', 'value', 'config_type', 'description')
        }),
        ('Scope', {
            'fields': ('service_name', 'environment')
        }),
        ('Security', {
            'fields': ('is_sensitive', 'is_encrypted')
        }),
        ('Version Control', {
            'fields': ('version', 'previous_value', 'expires_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['encrypt_sensitive_configs', 'decrypt_configs']
    
    def encrypt_sensitive_configs(self, request, queryset):
        updated = queryset.filter(is_sensitive=True).update(is_encrypted=True)
        self.message_user(request, f'{updated} sensitive configurations marked as encrypted.')
    encrypt_sensitive_configs.short_description = 'Mark sensitive configurations as encrypted'
    
    def decrypt_configs(self, request, queryset):
        updated = queryset.update(is_encrypted=False)
        self.message_user(request, f'{updated} configurations marked as unencrypted.')
    decrypt_configs.short_description = 'Mark configurations as unencrypted'


@admin.register(ConfigurationHistory)
class ConfigurationHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'config_key', 'change_type', 'changed_by', 'changed_at'
    ]
    list_filter = ['change_type', 'changed_at']
    search_fields = ['configuration__key', 'changed_by', 'change_reason']
    readonly_fields = ['id', 'changed_at']
    fieldsets = (
        ('Change Information', {
            'fields': ('configuration', 'change_type', 'changed_by', 'change_reason')
        }),
        ('Values', {
            'fields': ('old_value', 'new_value'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('changed_at',),
            'classes': ('collapse',)
        }),
    )
    actions = ['delete_old_history']
    
    def config_key(self, obj):
        return obj.configuration.key
    config_key.short_description = 'Configuration Key'
    
    def delete_old_history(self, request, queryset):
        # Delete history older than 90 days
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=90)
        old_history = ConfigurationHistory.objects.filter(changed_at__lt=cutoff_date)
        count = old_history.count()
        old_history.delete()
        self.message_user(request, f'{count} old history records deleted.')
    delete_old_history.short_description = 'Delete history older than 90 days'


@admin.register(ServiceDependency)
class ServiceDependencyAdmin(admin.ModelAdmin):
    list_display = [
        'source_service_name', 'target_service_name', 'dependency_type',
        'is_active', 'created_at'
    ]
    list_filter = ['dependency_type', 'is_active', 'created_at']
    search_fields = ['source_service__service_name', 'target_service__service_name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Dependency Information', {
            'fields': ('source_service', 'target_service', 'dependency_type', 'description')
        }),
        ('Status', {
            'fields': ('is_active', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['activate_dependencies', 'deactivate_dependencies']
    
    def source_service_name(self, obj):
        return obj.source_service.service_name
    source_service_name.short_description = 'Source Service'
    
    def target_service_name(self, obj):
        return obj.target_service.service_name
    target_service_name.short_description = 'Target Service'
    
    def activate_dependencies(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} dependencies activated.')
    activate_dependencies.short_description = 'Activate selected dependencies'
    
    def deactivate_dependencies(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} dependencies deactivated.')
    deactivate_dependencies.short_description = 'Deactivate selected dependencies'


@admin.register(ServiceMetrics)
class ServiceMetricsAdmin(admin.ModelAdmin):
    list_display = [
        'service_name', 'instance_id', 'cpu_usage', 'memory_usage',
        'request_count', 'error_count', 'recorded_at'
    ]
    list_filter = ['recorded_at']
    search_fields = ['service_instance__service__service_name', 'service_instance__instance_id']
    readonly_fields = ['id', 'recorded_at']
    fieldsets = (
        ('Performance Metrics', {
            'fields': ('service_instance', 'cpu_usage', 'memory_usage', 'disk_usage', 'network_io')
        }),
        ('Application Metrics', {
            'fields': ('request_count', 'error_count', 'response_time_avg', 'response_time_p95', 'response_time_p99')
        }),
        ('Custom Metrics', {
            'fields': ('custom_metrics',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('recorded_at',),
            'classes': ('collapse',)
        }),
    )
    actions = ['delete_old_metrics']
    
    def service_name(self, obj):
        return obj.service_instance.service.service_name
    service_name.short_description = 'Service'
    
    def instance_id(self, obj):
        return obj.service_instance.instance_id
    instance_id.short_description = 'Instance'
    
    def delete_old_metrics(self, request, queryset):
        # Delete metrics older than 30 days
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=30)
        old_metrics = ServiceMetrics.objects.filter(recorded_at__lt=cutoff_date)
        count = old_metrics.count()
        old_metrics.delete()
        self.message_user(request, f'{count} old metrics deleted.')
    delete_old_metrics.short_description = 'Delete metrics older than 30 days'
