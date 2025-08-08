from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .models import (
    AuditLog, SecurityEvent, PerformanceMetric, DataChangeLog, 
    APIAuditLog, DistributedTrace, AuditConfiguration
)


class AuditLogSerializer(serializers.ModelSerializer):
    """Standard serializer for AuditLog"""
    service_name_display = serializers.CharField(source='get_service_name_display', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = '__all__'
        read_only_fields = ('id', 'timestamp')


class AuditLogCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating audit logs"""
    
    class Meta:
        model = AuditLog
        fields = [
            'level', 'log_type', 'service_name', 'user_id', 'session_id',
            'request_id', 'trace_id', 'span_id', 'ip_address', 'user_agent',
            'request_method', 'request_path', 'request_params', 'request_headers',
            'request_body', 'response_status', 'response_time_ms', 'response_size',
            'response_body', 'action', 'resource_type', 'resource_id',
            'old_values', 'new_values', 'changed_fields', 'message', 'details',
            'metadata', 'error_type', 'error_message', 'stack_trace'
        ]


class AuditLogSearchSerializer(serializers.Serializer):
    """Serializer for audit log search parameters"""
    service_name = serializers.CharField(required=False)
    user_id = serializers.UUIDField(required=False)
    log_type = serializers.ChoiceField(choices=AuditLog.LOG_TYPE, required=False)
    level = serializers.ChoiceField(choices=AuditLog.LOG_LEVEL, required=False)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    trace_id = serializers.UUIDField(required=False)
    request_id = serializers.UUIDField(required=False)
    action = serializers.CharField(required=False)
    resource_type = serializers.CharField(required=False)
    resource_id = serializers.UUIDField(required=False)
    limit = serializers.IntegerField(default=100, max_value=1000)
    offset = serializers.IntegerField(default=0)


class SecurityEventSerializer(serializers.ModelSerializer):
    """Standard serializer for SecurityEvent"""
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = SecurityEvent
        fields = '__all__'
        read_only_fields = ('id', 'timestamp')


class SecurityEventCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating security events"""
    
    class Meta:
        model = SecurityEvent
        fields = [
            'event_type', 'severity', 'user_id', 'ip_address', 'user_agent',
            'session_id', 'description', 'details', 'metadata', 'risk_score',
            'risk_factors'
        ]


class SecurityEventUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating security events (e.g., marking as resolved)"""
    
    class Meta:
        model = SecurityEvent
        fields = ['is_resolved', 'resolved_by', 'resolution_notes']


class SecurityEventSearchSerializer(serializers.Serializer):
    """Serializer for security event search parameters"""
    event_type = serializers.ChoiceField(choices=SecurityEvent.EVENT_TYPE, required=False)
    severity = serializers.ChoiceField(choices=SecurityEvent.SEVERITY, required=False)
    user_id = serializers.UUIDField(required=False)
    ip_address = serializers.IPAddressField(required=False)
    is_resolved = serializers.BooleanField(required=False)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    risk_score_min = serializers.IntegerField(required=False, min_value=0, max_value=100)
    risk_score_max = serializers.IntegerField(required=False, min_value=0, max_value=100)
    limit = serializers.IntegerField(default=100, max_value=1000)
    offset = serializers.IntegerField(default=0)


class PerformanceMetricSerializer(serializers.ModelSerializer):
    """Standard serializer for PerformanceMetric"""
    metric_type_display = serializers.CharField(source='get_metric_type_display', read_only=True)
    
    class Meta:
        model = PerformanceMetric
        fields = '__all__'
        read_only_fields = ('id', 'timestamp')


class PerformanceMetricCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating performance metrics"""
    
    class Meta:
        model = PerformanceMetric
        fields = [
            'service_name', 'metric_type', 'metric_name', 'value', 'unit',
            'endpoint', 'method', 'user_id', 'session_id', 'tags', 'metadata'
        ]


class PerformanceMetricSearchSerializer(serializers.Serializer):
    """Serializer for performance metric search parameters"""
    service_name = serializers.CharField(required=False)
    metric_type = serializers.ChoiceField(choices=PerformanceMetric.METRIC_TYPE, required=False)
    metric_name = serializers.CharField(required=False)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    user_id = serializers.UUIDField(required=False)
    endpoint = serializers.CharField(required=False)
    limit = serializers.IntegerField(default=100, max_value=1000)
    offset = serializers.IntegerField(default=0)


class DataChangeLogSerializer(serializers.ModelSerializer):
    """Standard serializer for DataChangeLog"""
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)
    
    class Meta:
        model = DataChangeLog
        fields = '__all__'
        read_only_fields = ('id', 'timestamp')


class DataChangeLogCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating data change logs"""
    
    class Meta:
        model = DataChangeLog
        fields = [
            'user_id', 'service_name', 'change_type', 'model_name', 'object_id',
            'content_type', 'old_values', 'new_values', 'changed_fields',
            'request_id', 'session_id', 'ip_address', 'reason', 'metadata'
        ]


class DataChangeLogSearchSerializer(serializers.Serializer):
    """Serializer for data change log search parameters"""
    service_name = serializers.CharField(required=False)
    change_type = serializers.ChoiceField(choices=DataChangeLog.CHANGE_TYPE, required=False)
    model_name = serializers.CharField(required=False)
    user_id = serializers.UUIDField(required=False)
    object_id = serializers.UUIDField(required=False)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    limit = serializers.IntegerField(default=100, max_value=1000)
    offset = serializers.IntegerField(default=0)


class APIAuditLogSerializer(serializers.ModelSerializer):
    """Standard serializer for APIAuditLog"""
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    status_category_display = serializers.CharField(source='get_status_category_display', read_only=True)
    
    class Meta:
        model = APIAuditLog
        fields = '__all__'
        read_only_fields = ('id', 'timestamp')


class APIAuditLogCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating API audit logs"""
    
    class Meta:
        model = APIAuditLog
        fields = [
            'service_name', 'endpoint', 'method', 'user_id', 'session_id',
            'request_id', 'trace_id', 'span_id', 'ip_address', 'user_agent',
            'referer', 'request_headers', 'request_params', 'request_body',
            'request_size', 'response_status', 'status_category', 'response_time_ms',
            'response_size', 'response_body', 'error_type', 'error_message',
            'stack_trace', 'database_queries', 'cache_hits', 'cache_misses',
            'metadata'
        ]


class APIAuditLogSearchSerializer(serializers.Serializer):
    """Serializer for API audit log search parameters"""
    service_name = serializers.CharField(required=False)
    method = serializers.ChoiceField(choices=APIAuditLog.HTTP_METHOD, required=False)
    endpoint = serializers.CharField(required=False)
    response_status = serializers.IntegerField(required=False)
    status_category = serializers.ChoiceField(choices=APIAuditLog.STATUS_CATEGORY, required=False)
    user_id = serializers.UUIDField(required=False)
    trace_id = serializers.UUIDField(required=False)
    request_id = serializers.UUIDField(required=False)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    response_time_min = serializers.IntegerField(required=False)
    response_time_max = serializers.IntegerField(required=False)
    limit = serializers.IntegerField(default=100, max_value=1000)
    offset = serializers.IntegerField(default=0)


class DistributedTraceSerializer(serializers.ModelSerializer):
    """Standard serializer for DistributedTrace"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = DistributedTrace
        fields = '__all__'
        read_only_fields = ('id', 'start_time')


class DistributedTraceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating distributed traces"""
    
    class Meta:
        model = DistributedTrace
        fields = [
            'trace_id', 'parent_span_id', 'span_id', 'service_name',
            'operation_name', 'start_time', 'end_time', 'duration_ms',
            'status', 'user_id', 'session_id', 'request_id', 'tags',
            'metadata', 'error_type', 'error_message', 'stack_trace'
        ]


class DistributedTraceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating distributed traces (e.g., completing spans)"""
    
    class Meta:
        model = DistributedTrace
        fields = ['end_time', 'duration_ms', 'status', 'error_type', 'error_message', 'stack_trace']


class DistributedTraceSearchSerializer(serializers.Serializer):
    """Serializer for distributed trace search parameters"""
    trace_id = serializers.UUIDField(required=False)
    span_id = serializers.UUIDField(required=False)
    service_name = serializers.CharField(required=False)
    operation_name = serializers.CharField(required=False)
    status = serializers.ChoiceField(choices=DistributedTrace.TRACE_STATUS, required=False)
    user_id = serializers.UUIDField(required=False)
    request_id = serializers.UUIDField(required=False)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    duration_min = serializers.IntegerField(required=False)
    duration_max = serializers.IntegerField(required=False)
    limit = serializers.IntegerField(default=100, max_value=1000)
    offset = serializers.IntegerField(default=0)


class AuditConfigurationSerializer(serializers.ModelSerializer):
    """Standard serializer for AuditConfiguration"""
    log_level_display = serializers.CharField(source='get_log_level_display', read_only=True)
    
    class Meta:
        model = AuditConfiguration
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class AuditConfigurationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating audit configurations"""
    
    class Meta:
        model = AuditConfiguration
        fields = [
            'service_name', 'enabled', 'log_level', 'log_types',
            'retention_days', 'archive_enabled', 'archive_after_days',
            'batch_size', 'flush_interval_seconds', 'mask_sensitive_fields',
            'exclude_paths', 'exclude_methods', 'alert_on_errors',
            'alert_on_security_events', 'alert_recipients'
        ]


class AuditConfigurationUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating audit configurations"""
    
    class Meta:
        model = AuditConfiguration
        fields = [
            'enabled', 'log_level', 'log_types', 'retention_days',
            'archive_enabled', 'archive_after_days', 'batch_size',
            'flush_interval_seconds', 'mask_sensitive_fields',
            'exclude_paths', 'exclude_methods', 'alert_on_errors',
            'alert_on_security_events', 'alert_recipients'
        ]


# Specialized serializers for specific use cases
class AuditStatsSerializer(serializers.Serializer):
    """Serializer for audit statistics"""
    total_logs = serializers.IntegerField()
    logs_by_level = serializers.DictField()
    logs_by_type = serializers.DictField()
    logs_by_service = serializers.DictField()
    recent_errors = serializers.ListField()
    performance_summary = serializers.DictField()


class SecurityEventStatsSerializer(serializers.Serializer):
    """Serializer for security event statistics"""
    total_events = serializers.IntegerField()
    events_by_type = serializers.DictField()
    events_by_severity = serializers.DictField()
    events_by_ip = serializers.DictField()
    unresolved_events = serializers.IntegerField()
    high_risk_events = serializers.IntegerField()


class PerformanceStatsSerializer(serializers.Serializer):
    """Serializer for performance statistics"""
    avg_response_time = serializers.FloatField()
    max_response_time = serializers.FloatField()
    min_response_time = serializers.FloatField()
    total_requests = serializers.IntegerField()
    error_rate = serializers.FloatField()
    throughput = serializers.FloatField()
    metrics_by_service = serializers.DictField()


class TraceStatsSerializer(serializers.Serializer):
    """Serializer for distributed trace statistics"""
    total_traces = serializers.IntegerField()
    active_traces = serializers.IntegerField()
    completed_traces = serializers.IntegerField()
    failed_traces = serializers.IntegerField()
    avg_duration = serializers.FloatField()
    max_duration = serializers.FloatField()
    traces_by_service = serializers.DictField()


class AuditExportSerializer(serializers.Serializer):
    """Serializer for audit data export"""
    format = serializers.ChoiceField(choices=['json', 'csv', 'xml'])
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField()
    log_types = serializers.ListField(required=False)
    services = serializers.ListField(required=False)
    include_sensitive_data = serializers.BooleanField(default=False)


class AuditAlertSerializer(serializers.Serializer):
    """Serializer for audit alerts"""
    alert_type = serializers.ChoiceField(choices=['error_threshold', 'security_event', 'performance_degradation'])
    threshold = serializers.FloatField()
    time_window_minutes = serializers.IntegerField()
    recipients = serializers.ListField()
    enabled = serializers.BooleanField(default=True)
