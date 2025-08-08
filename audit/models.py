import uuid
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class AuditLog(models.Model):
    """Main audit log model for tracking all system activities"""
    LOG_LEVEL = (
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    )
    
    LOG_TYPE = (
        ('user_action', 'User Action'),
        ('api_call', 'API Call'),
        ('system_event', 'System Event'),
        ('security_event', 'Security Event'),
        ('data_change', 'Data Change'),
        ('performance', 'Performance'),
        ('error', 'Error'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=10, choices=LOG_LEVEL, default='info')
    log_type = models.CharField(max_length=20, choices=LOG_TYPE)
    service_name = models.CharField(max_length=50)  # e.g., 'products', 'orders', 'payments'
    user_id = models.UUIDField(null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    request_id = models.UUIDField(null=True, blank=True)  # For distributed tracing
    trace_id = models.UUIDField(null=True, blank=True)  # For distributed tracing
    span_id = models.UUIDField(null=True, blank=True)  # For distributed tracing
    
    # Request details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    request_path = models.TextField(blank=True)
    request_params = models.JSONField(default=dict, blank=True)
    request_headers = models.JSONField(default=dict, blank=True)
    request_body = models.TextField(blank=True)
    
    # Response details
    response_status = models.IntegerField(null=True, blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    response_size = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    
    # Action details
    action = models.CharField(max_length=100, blank=True)  # e.g., 'create', 'update', 'delete'
    resource_type = models.CharField(max_length=50, blank=True)  # e.g., 'Product', 'Order'
    resource_id = models.UUIDField(null=True, blank=True)
    
    # Content type for generic relations
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Change tracking
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    
    # Message and context
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Error tracking
    error_type = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    stack_trace = models.TextField(blank=True)
    
    class Meta:
        db_table = 'audit_logs'
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['service_name']),
            models.Index(fields=['user_id']),
            models.Index(fields=['log_type']),
            models.Index(fields=['level']),
            models.Index(fields=['trace_id']),
            models.Index(fields=['request_id']),
        ]
        ordering = ['-timestamp']


class SecurityEvent(models.Model):
    """Specialized model for security-related events"""
    EVENT_TYPE = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('failed_login', 'Failed Login'),
        ('password_change', 'Password Change'),
        ('password_reset', 'Password Reset'),
        ('account_lockout', 'Account Lockout'),
        ('permission_denied', 'Permission Denied'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('data_access', 'Data Access'),
        ('data_export', 'Data Export'),
        ('api_key_usage', 'API Key Usage'),
        ('session_timeout', 'Session Timeout'),
    )
    
    SEVERITY = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE)
    severity = models.CharField(max_length=10, choices=SEVERITY, default='medium')
    user_id = models.UUIDField(null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    
    # Event details
    description = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Risk assessment
    risk_score = models.IntegerField(default=0)  # 0-100
    risk_factors = models.JSONField(default=list, blank=True)
    
    # Response tracking
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.UUIDField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'security_events'
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['event_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['user_id']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['is_resolved']),
        ]
        ordering = ['-timestamp']


class PerformanceMetric(models.Model):
    """Model for tracking performance metrics"""
    METRIC_TYPE = (
        ('response_time', 'Response Time'),
        ('throughput', 'Throughput'),
        ('error_rate', 'Error Rate'),
        ('cpu_usage', 'CPU Usage'),
        ('memory_usage', 'Memory Usage'),
        ('disk_usage', 'Disk Usage'),
        ('network_io', 'Network I/O'),
        ('database_query', 'Database Query'),
        ('cache_hit_rate', 'Cache Hit Rate'),
        ('queue_length', 'Queue Length'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    service_name = models.CharField(max_length=50)
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPE)
    metric_name = models.CharField(max_length=100)
    value = models.FloatField()
    unit = models.CharField(max_length=20, blank=True)  # e.g., 'ms', 'req/s', '%'
    
    # Context
    endpoint = models.CharField(max_length=200, blank=True)
    method = models.CharField(max_length=10, blank=True)
    user_id = models.UUIDField(null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    
    # Additional context
    tags = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'performance_metrics'
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['service_name']),
            models.Index(fields=['metric_type']),
            models.Index(fields=['metric_name']),
        ]
        ordering = ['-timestamp']


class DataChangeLog(models.Model):
    """Specialized model for tracking data changes"""
    CHANGE_TYPE = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('bulk_create', 'Bulk Create'),
        ('bulk_update', 'Bulk Update'),
        ('bulk_delete', 'Bulk Delete'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    user_id = models.UUIDField(null=True, blank=True)
    service_name = models.CharField(max_length=50)
    
    # Change details
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPE)
    model_name = models.CharField(max_length=100)
    object_id = models.UUIDField(null=True, blank=True)
    
    # Content type for generic relations
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Change data
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    
    # Context
    request_id = models.UUIDField(null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Additional info
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'data_change_logs'
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['service_name']),
            models.Index(fields=['change_type']),
            models.Index(fields=['model_name']),
            models.Index(fields=['user_id']),
        ]
        ordering = ['-timestamp']


class APIAuditLog(models.Model):
    """Specialized model for API call auditing"""
    HTTP_METHOD = (
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
        ('HEAD', 'HEAD'),
        ('OPTIONS', 'OPTIONS'),
    )
    
    STATUS_CATEGORY = (
        ('1xx', 'Informational'),
        ('2xx', 'Success'),
        ('3xx', 'Redirection'),
        ('4xx', 'Client Error'),
        ('5xx', 'Server Error'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Request details
    service_name = models.CharField(max_length=50)
    endpoint = models.CharField(max_length=500)
    method = models.CharField(max_length=10, choices=HTTP_METHOD)
    user_id = models.UUIDField(null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    
    # Request data
    request_id = models.UUIDField(null=True, blank=True)
    trace_id = models.UUIDField(null=True, blank=True)
    span_id = models.UUIDField(null=True, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referer = models.URLField(blank=True)
    
    # Request content
    request_headers = models.JSONField(default=dict, blank=True)
    request_params = models.JSONField(default=dict, blank=True)
    request_body = models.TextField(blank=True)
    request_size = models.IntegerField(null=True, blank=True)
    
    # Response details
    response_status = models.IntegerField()
    status_category = models.CharField(max_length=3, choices=STATUS_CATEGORY)
    response_time_ms = models.IntegerField()
    response_size = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    
    # Error tracking
    error_type = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    stack_trace = models.TextField(blank=True)
    
    # Performance
    database_queries = models.IntegerField(default=0)
    cache_hits = models.IntegerField(default=0)
    cache_misses = models.IntegerField(default=0)
    
    # Additional context
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'api_audit_logs'
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['service_name']),
            models.Index(fields=['method']),
            models.Index(fields=['response_status']),
            models.Index(fields=['user_id']),
            models.Index(fields=['trace_id']),
            models.Index(fields=['request_id']),
        ]
        ordering = ['-timestamp']


class DistributedTrace(models.Model):
    """Model for distributed tracing across microservices"""
    TRACE_STATUS = (
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trace_id = models.UUIDField(unique=True)  # Global trace ID
    parent_span_id = models.UUIDField(null=True, blank=True)
    span_id = models.UUIDField(unique=True)
    
    # Service details
    service_name = models.CharField(max_length=50)
    operation_name = models.CharField(max_length=100)
    
    # Timing
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=10, choices=TRACE_STATUS, default='active')
    
    # Context
    user_id = models.UUIDField(null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    request_id = models.UUIDField(null=True, blank=True)
    
    # Tags and metadata
    tags = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Error tracking
    error_type = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    stack_trace = models.TextField(blank=True)
    
    class Meta:
        db_table = 'distributed_traces'
        indexes = [
            models.Index(fields=['trace_id']),
            models.Index(fields=['span_id']),
            models.Index(fields=['service_name']),
            models.Index(fields=['start_time']),
            models.Index(fields=['status']),
        ]
        ordering = ['-start_time']


class AuditConfiguration(models.Model):
    """Configuration model for audit logging settings"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_name = models.CharField(max_length=50, unique=True)
    
    # Logging settings
    enabled = models.BooleanField(default=True)
    log_level = models.CharField(max_length=10, choices=AuditLog.LOG_LEVEL, default='info')
    log_types = models.JSONField(default=list)  # List of log types to capture
    
    # Retention settings
    retention_days = models.IntegerField(default=90)
    archive_enabled = models.BooleanField(default=False)
    archive_after_days = models.IntegerField(default=30)
    
    # Performance settings
    batch_size = models.IntegerField(default=100)
    flush_interval_seconds = models.IntegerField(default=60)
    
    # Security settings
    mask_sensitive_fields = models.JSONField(default=list)  # Fields to mask in logs
    exclude_paths = models.JSONField(default=list)  # Paths to exclude from logging
    exclude_methods = models.JSONField(default=list)  # HTTP methods to exclude
    
    # Notification settings
    alert_on_errors = models.BooleanField(default=True)
    alert_on_security_events = models.BooleanField(default=True)
    alert_recipients = models.JSONField(default=list)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'audit_configurations'
        ordering = ['service_name']
