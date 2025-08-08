from rest_framework import serializers
from .models import (
    ServiceRegistry, ServiceInstance, HealthCheck, Configuration,
    ConfigurationHistory, ServiceDependency, ServiceMetrics
)


class ServiceRegistrySerializer(serializers.ModelSerializer):
    """Serializer for ServiceRegistry model"""
    instances_count = serializers.SerializerMethodField()
    healthy_instances_count = serializers.SerializerMethodField()
    last_health_check_status = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceRegistry
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'last_heartbeat')
    
    def get_instances_count(self, obj):
        return obj.instances.count()
    
    def get_healthy_instances_count(self, obj):
        return obj.instances.filter(status='healthy').count()
    
    def get_last_health_check_status(self, obj):
        latest_check = obj.instances.filter(
            health_checks__isnull=False
        ).order_by('-health_checks__checked_at').first()
        if latest_check and latest_check.health_checks.exists():
            return latest_check.health_checks.first().status
        return None


class ServiceRegistryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ServiceRegistry"""
    class Meta:
        model = ServiceRegistry
        fields = [
            'service_name', 'service_type', 'version', 'description',
            'base_url', 'health_check_url', 'api_docs_url', 'status',
            'is_public', 'is_secure', 'capabilities', 'dependencies',
            'config', 'environment'
        ]


class ServiceRegistryUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating ServiceRegistry"""
    class Meta:
        model = ServiceRegistry
        fields = [
            'description', 'base_url', 'health_check_url', 'api_docs_url',
            'status', 'is_public', 'is_secure', 'capabilities', 'dependencies',
            'config', 'environment'
        ]


class ServiceInstanceSerializer(serializers.ModelSerializer):
    """Serializer for ServiceInstance model"""
    service_name = serializers.CharField(source='service.service_name', read_only=True)
    last_health_check_status = serializers.SerializerMethodField()
    last_health_check_time = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceInstance
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'last_heartbeat')
    
    def get_last_health_check_status(self, obj):
        latest_check = obj.health_checks.order_by('-checked_at').first()
        return latest_check.status if latest_check else None
    
    def get_last_health_check_time(self, obj):
        latest_check = obj.health_checks.order_by('-checked_at').first()
        return latest_check.checked_at if latest_check else None


class ServiceInstanceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ServiceInstance"""
    class Meta:
        model = ServiceInstance
        fields = [
            'service', 'instance_id', 'host', 'port', 'protocol',
            'status', 'is_primary', 'health_check_interval',
            'health_check_timeout', 'metadata', 'load_balancer_weight'
        ]


class ServiceInstanceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating ServiceInstance"""
    class Meta:
        model = ServiceInstance
        fields = [
            'status', 'is_primary', 'health_check_interval',
            'health_check_timeout', 'metadata', 'load_balancer_weight'
        ]


class HealthCheckSerializer(serializers.ModelSerializer):
    """Serializer for HealthCheck model"""
    service_name = serializers.CharField(source='service_instance.service.service_name', read_only=True)
    instance_id = serializers.CharField(source='service_instance.instance_id', read_only=True)
    
    class Meta:
        model = HealthCheck
        fields = '__all__'
        read_only_fields = ('id', 'checked_at')


class HealthCheckCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating HealthCheck"""
    class Meta:
        model = HealthCheck
        fields = [
            'service_instance', 'status', 'response_time_ms',
            'response_code', 'error_message', 'response_body', 'metadata'
        ]


class ConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for Configuration model"""
    class Meta:
        model = Configuration
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'version', 'previous_value')


class ConfigurationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Configuration"""
    class Meta:
        model = Configuration
        fields = [
            'key', 'value', 'config_type', 'service_name', 'environment',
            'description', 'is_sensitive', 'is_encrypted', 'expires_at'
        ]


class ConfigurationUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Configuration"""
    class Meta:
        model = Configuration
        fields = [
            'value', 'description', 'is_sensitive', 'is_encrypted', 'expires_at'
        ]


class ConfigurationHistorySerializer(serializers.ModelSerializer):
    """Serializer for ConfigurationHistory model"""
    config_key = serializers.CharField(source='configuration.key', read_only=True)
    
    class Meta:
        model = ConfigurationHistory
        fields = '__all__'
        read_only_fields = ('id', 'changed_at')


class ServiceDependencySerializer(serializers.ModelSerializer):
    """Serializer for ServiceDependency model"""
    source_service_name = serializers.CharField(source='source_service.service_name', read_only=True)
    target_service_name = serializers.CharField(source='target_service.service_name', read_only=True)
    
    class Meta:
        model = ServiceDependency
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class ServiceDependencyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ServiceDependency"""
    class Meta:
        model = ServiceDependency
        fields = [
            'source_service', 'target_service', 'dependency_type',
            'description', 'is_active', 'metadata'
        ]


class ServiceMetricsSerializer(serializers.ModelSerializer):
    """Serializer for ServiceMetrics model"""
    service_name = serializers.CharField(source='service_instance.service.service_name', read_only=True)
    instance_id = serializers.CharField(source='service_instance.instance_id', read_only=True)
    
    class Meta:
        model = ServiceMetrics
        fields = '__all__'
        read_only_fields = ('id', 'recorded_at')


class ServiceMetricsCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ServiceMetrics"""
    class Meta:
        model = ServiceMetrics
        fields = [
            'service_instance', 'cpu_usage', 'memory_usage', 'disk_usage',
            'network_io', 'request_count', 'error_count', 'response_time_avg',
            'response_time_p95', 'response_time_p99', 'custom_metrics'
        ]


# Specialized serializers for specific use cases
class ServiceRegistryListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing services"""
    instances_count = serializers.SerializerMethodField()
    healthy_instances_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceRegistry
        fields = [
            'id', 'service_name', 'service_type', 'version', 'status',
            'base_url', 'environment', 'instances_count', 'healthy_instances_count',
            'last_heartbeat', 'created_at'
        ]
    
    def get_instances_count(self, obj):
        return obj.instances.count()
    
    def get_healthy_instances_count(self, obj):
        return obj.instances.filter(status='healthy').count()


class ServiceInstanceListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing service instances"""
    service_name = serializers.CharField(source='service.service_name', read_only=True)
    last_health_check_status = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceInstance
        fields = [
            'id', 'instance_id', 'service_name', 'host', 'port', 'status',
            'is_primary', 'last_health_check', 'last_heartbeat', 'created_at'
        ]
    
    def get_last_health_check_status(self, obj):
        latest_check = obj.health_checks.order_by('-checked_at').first()
        return latest_check.status if latest_check else None


class ConfigurationListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing configurations"""
    class Meta:
        model = Configuration
        fields = [
            'id', 'key', 'config_type', 'service_name', 'environment',
            'is_sensitive', 'is_encrypted', 'version', 'updated_at'
        ]


class ServiceHealthSummarySerializer(serializers.Serializer):
    """Serializer for service health summary"""
    service_name = serializers.CharField()
    total_instances = serializers.IntegerField()
    healthy_instances = serializers.IntegerField()
    unhealthy_instances = serializers.IntegerField()
    maintenance_instances = serializers.IntegerField()
    overall_status = serializers.CharField()
    last_health_check = serializers.DateTimeField(allow_null=True)
    average_response_time = serializers.FloatField(allow_null=True)


class ServiceDiscoveryStatsSerializer(serializers.Serializer):
    """Serializer for service discovery statistics"""
    total_services = serializers.IntegerField()
    active_services = serializers.IntegerField()
    total_instances = serializers.IntegerField()
    healthy_instances = serializers.IntegerField()
    total_configurations = serializers.IntegerField()
    services_by_type = serializers.DictField()
    services_by_environment = serializers.DictField()


class ConfigurationSearchSerializer(serializers.Serializer):
    """Serializer for configuration search"""
    key = serializers.CharField(required=False)
    config_type = serializers.CharField(required=False)
    service_name = serializers.CharField(required=False)
    environment = serializers.CharField(required=False)
    is_sensitive = serializers.BooleanField(required=False)


class ServiceSearchSerializer(serializers.Serializer):
    """Serializer for service search"""
    service_name = serializers.CharField(required=False)
    service_type = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    environment = serializers.CharField(required=False)
    is_public = serializers.BooleanField(required=False)


class ServiceRegistrationSerializer(serializers.Serializer):
    """Serializer for service registration"""
    service_name = serializers.CharField()
    service_type = serializers.CharField()
    version = serializers.CharField()
    base_url = serializers.URLField()
    health_check_url = serializers.URLField()
    instance_id = serializers.CharField()
    host = serializers.CharField()
    port = serializers.IntegerField()
    protocol = serializers.CharField(default='http')
    capabilities = serializers.DictField(required=False)
    dependencies = serializers.ListField(required=False)
    metadata = serializers.DictField(required=False)


class ServiceHeartbeatSerializer(serializers.Serializer):
    """Serializer for service heartbeat"""
    instance_id = serializers.CharField()
    status = serializers.CharField()
    metadata = serializers.DictField(required=False)
    metrics = serializers.DictField(required=False)


class ConfigurationBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk configuration updates"""
    configurations = serializers.ListField(
        child=serializers.DictField()
    )
    environment = serializers.CharField(required=False)
    service_name = serializers.CharField(required=False)
    change_reason = serializers.CharField(required=False)
