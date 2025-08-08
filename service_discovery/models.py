import uuid
import json
from django.db import models
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder


class ServiceRegistry(models.Model):
    """Model for registering microservices"""
    SERVICE_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Maintenance'),
        ('deprecated', 'Deprecated'),
    ]
    
    SERVICE_TYPE_CHOICES = [
        ('api', 'API Service'),
        ('worker', 'Worker Service'),
        ('gateway', 'Gateway Service'),
        ('database', 'Database Service'),
        ('cache', 'Cache Service'),
        ('message_queue', 'Message Queue Service'),
        ('monitoring', 'Monitoring Service'),
        ('storage', 'Storage Service'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_name = models.CharField(max_length=100, unique=True)
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, default='api')
    version = models.CharField(max_length=20, default='1.0.0')
    description = models.TextField(blank=True)
    
    # Service endpoints
    base_url = models.URLField()
    health_check_url = models.URLField()
    api_docs_url = models.URLField(blank=True)
    
    # Service metadata
    status = models.CharField(max_length=20, choices=SERVICE_STATUS_CHOICES, default='active')
    is_public = models.BooleanField(default=True)
    is_secure = models.BooleanField(default=True)
    
    # Service capabilities
    capabilities = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    service_dependencies = models.JSONField(default=list, encoder=DjangoJSONEncoder)
    
    # Service configuration
    config = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    environment = models.CharField(max_length=50, default='production')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'service_registry'
        verbose_name_plural = 'Service Registries'
        indexes = [
            models.Index(fields=['service_name']),
            models.Index(fields=['service_type']),
            models.Index(fields=['status']),
            models.Index(fields=['environment']),
            models.Index(fields=['last_heartbeat']),
        ]
        ordering = ['service_name']


class ServiceInstance(models.Model):
    """Model for individual service instances"""
    INSTANCE_STATUS_CHOICES = [
        ('healthy', 'Healthy'),
        ('unhealthy', 'Unhealthy'),
        ('starting', 'Starting'),
        ('stopping', 'Stopping'),
        ('maintenance', 'Maintenance'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(ServiceRegistry, on_delete=models.CASCADE, related_name='instances')
    instance_id = models.CharField(max_length=100, unique=True)
    
    # Instance details
    host = models.CharField(max_length=255)
    port = models.IntegerField()
    protocol = models.CharField(max_length=10, default='http')
    
    # Instance status
    status = models.CharField(max_length=20, choices=INSTANCE_STATUS_CHOICES, default='starting')
    is_primary = models.BooleanField(default=False)
    
    # Health check info
    last_health_check = models.DateTimeField(null=True, blank=True)
    health_check_interval = models.IntegerField(default=30)  # seconds
    health_check_timeout = models.IntegerField(default=5)    # seconds
    
    # Instance metadata
    metadata = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    load_balancer_weight = models.IntegerField(default=100)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'service_instances'
        indexes = [
            models.Index(fields=['instance_id']),
            models.Index(fields=['service']),
            models.Index(fields=['status']),
            models.Index(fields=['last_heartbeat']),
        ]
        ordering = ['service', 'instance_id']


class HealthCheck(models.Model):
    """Model for tracking service health checks"""
    CHECK_STATUS_CHOICES = [
        ('success', 'Success'),
        ('failure', 'Failure'),
        ('timeout', 'Timeout'),
        ('error', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_instance = models.ForeignKey(ServiceInstance, on_delete=models.CASCADE, related_name='health_checks')
    
    # Check details
    status = models.CharField(max_length=20, choices=CHECK_STATUS_CHOICES)
    response_time_ms = models.IntegerField()
    response_code = models.IntegerField(null=True, blank=True)
    
    # Check metadata
    error_message = models.TextField(blank=True)
    response_body = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    
    # Timestamps
    checked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'health_checks'
        indexes = [
            models.Index(fields=['service_instance']),
            models.Index(fields=['status']),
            models.Index(fields=['checked_at']),
        ]
        ordering = ['-checked_at']


class Configuration(models.Model):
    """Model for centralized configuration management"""
    CONFIG_TYPE_CHOICES = [
        ('application', 'Application Config'),
        ('database', 'Database Config'),
        ('cache', 'Cache Config'),
        ('message_queue', 'Message Queue Config'),
        ('security', 'Security Config'),
        ('monitoring', 'Monitoring Config'),
        ('feature_flag', 'Feature Flag'),
    ]
    
    ENVIRONMENT_CHOICES = [
        ('development', 'Development'),
        ('staging', 'Staging'),
        ('production', 'Production'),
        ('testing', 'Testing'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=255, unique=True)
    value = models.TextField()
    config_type = models.CharField(max_length=20, choices=CONFIG_TYPE_CHOICES, default='application')
    
    # Configuration scope
    service_name = models.CharField(max_length=100, blank=True)  # Empty for global config
    environment = models.CharField(max_length=20, choices=ENVIRONMENT_CHOICES, default='production')
    
    # Configuration metadata
    description = models.TextField(blank=True)
    is_sensitive = models.BooleanField(default=False)
    is_encrypted = models.BooleanField(default=False)
    
    # Version control
    version = models.IntegerField(default=1)
    previous_value = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'configurations'
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['config_type']),
            models.Index(fields=['service_name']),
            models.Index(fields=['environment']),
            models.Index(fields=['updated_at']),
        ]
        ordering = ['key']


class ConfigurationHistory(models.Model):
    """Model for tracking configuration changes"""
    CHANGE_TYPE_CHOICES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('rollback', 'Rollback'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    configuration = models.ForeignKey(Configuration, on_delete=models.CASCADE, related_name='history')
    
    # Change details
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPE_CHOICES)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    
    # Change metadata
    changed_by = models.CharField(max_length=100, blank=True)
    change_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    
    # Timestamps
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'configuration_history'
        indexes = [
            models.Index(fields=['configuration']),
            models.Index(fields=['change_type']),
            models.Index(fields=['changed_at']),
        ]
        ordering = ['-changed_at']


class ServiceDependency(models.Model):
    """Model for tracking service dependencies"""
    DEPENDENCY_TYPE_CHOICES = [
        ('required', 'Required'),
        ('optional', 'Optional'),
        ('circular', 'Circular'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_service = models.ForeignKey(ServiceRegistry, on_delete=models.CASCADE, related_name='outgoing_dependencies')
    target_service = models.ForeignKey(ServiceRegistry, on_delete=models.CASCADE, related_name='incoming_dependencies')
    
    # Dependency details
    dependency_type = models.CharField(max_length=20, choices=DEPENDENCY_TYPE_CHOICES, default='required')
    description = models.TextField(blank=True)
    
    # Dependency metadata
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'service_dependencies'
        unique_together = ['source_service', 'target_service']
        indexes = [
            models.Index(fields=['source_service']),
            models.Index(fields=['target_service']),
            models.Index(fields=['dependency_type']),
        ]
        ordering = ['source_service', 'target_service']


class ServiceMetrics(models.Model):
    """Model for tracking service performance metrics"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_instance = models.ForeignKey(ServiceInstance, on_delete=models.CASCADE, related_name='metrics')
    
    # Performance metrics
    cpu_usage = models.FloatField(null=True, blank=True)
    memory_usage = models.FloatField(null=True, blank=True)
    disk_usage = models.FloatField(null=True, blank=True)
    network_io = models.FloatField(null=True, blank=True)
    
    # Application metrics
    request_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    response_time_avg = models.FloatField(null=True, blank=True)
    response_time_p95 = models.FloatField(null=True, blank=True)
    response_time_p99 = models.FloatField(null=True, blank=True)
    
    # Custom metrics
    custom_metrics = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    
    # Timestamps
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'service_metrics'
        indexes = [
            models.Index(fields=['service_instance']),
            models.Index(fields=['recorded_at']),
        ]
        ordering = ['-recorded_at']
