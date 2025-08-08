import uuid
import json
import requests
import redis
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q, Count, Avg, Max, Min, Sum
from .models import (
    ServiceRegistry, ServiceInstance, HealthCheck, Configuration,
    ConfigurationHistory, ServiceDependency, ServiceMetrics
)


class ServiceRegistryService:
    """Service for managing service registry"""
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    
    def register_service(self, service_data, instance_data):
        """Register a new service and its instance"""
        try:
            # Create or update service registry
            service, created = ServiceRegistry.objects.get_or_create(
                service_name=service_data['service_name'],
                defaults={
                    'service_type': service_data.get('service_type', 'api'),
                    'version': service_data.get('version', '1.0.0'),
                    'description': service_data.get('description', ''),
                    'base_url': service_data['base_url'],
                    'health_check_url': service_data['health_check_url'],
                    'api_docs_url': service_data.get('api_docs_url', ''),
                    'capabilities': service_data.get('capabilities', {}),
                    'dependencies': service_data.get('dependencies', []),
                    'config': service_data.get('config', {}),
                    'environment': service_data.get('environment', 'production'),
                }
            )
            
            if not created:
                # Update existing service
                for key, value in service_data.items():
                    if hasattr(service, key):
                        setattr(service, key, value)
                service.save()
            
            # Create service instance
            instance = ServiceInstance.objects.create(
                service=service,
                instance_id=instance_data['instance_id'],
                host=instance_data['host'],
                port=instance_data['port'],
                protocol=instance_data.get('protocol', 'http'),
                metadata=instance_data.get('metadata', {}),
                load_balancer_weight=instance_data.get('load_balancer_weight', 100)
            )
            
            # Update service heartbeat
            service.last_heartbeat = timezone.now()
            service.save()
            
            # Cache service info
            self._cache_service_info(service, instance)
            
            return service, instance
            
        except Exception as e:
            raise Exception(f"Failed to register service: {str(e)}")
    
    def deregister_service(self, service_name, instance_id):
        """Deregister a service instance"""
        try:
            instance = ServiceInstance.objects.get(
                service__service_name=service_name,
                instance_id=instance_id
            )
            
            # Remove from cache
            self._remove_from_cache(service_name, instance_id)
            
            # Delete instance
            instance.delete()
            
            # Check if service has no more instances
            service = ServiceRegistry.objects.get(service_name=service_name)
            if not service.instances.exists():
                service.status = 'inactive'
                service.save()
            
            return True
            
        except ServiceInstance.DoesNotExist:
            return False
        except Exception as e:
            raise Exception(f"Failed to deregister service: {str(e)}")
    
    def update_heartbeat(self, service_name, instance_id, status='healthy', metadata=None):
        """Update service heartbeat"""
        try:
            instance = ServiceInstance.objects.get(
                service__service_name=service_name,
                instance_id=instance_id
            )
            
            instance.last_heartbeat = timezone.now()
            instance.status = status
            if metadata:
                instance.metadata.update(metadata)
            instance.save()
            
            # Update service heartbeat
            service = instance.service
            service.last_heartbeat = timezone.now()
            service.save()
            
            return instance
            
        except ServiceInstance.DoesNotExist:
            return None
    
    def get_service_instances(self, service_name, healthy_only=True):
        """Get instances for a service"""
        queryset = ServiceInstance.objects.filter(service__service_name=service_name)
        
        if healthy_only:
            queryset = queryset.filter(status='healthy')
        
        return queryset.order_by('-is_primary', '-load_balancer_weight')
    
    def get_all_services(self, status=None, service_type=None, environment=None):
        """Get all services with optional filters"""
        queryset = ServiceRegistry.objects.all()
        
        if status:
            queryset = queryset.filter(status=status)
        if service_type:
            queryset = queryset.filter(service_type=service_type)
        if environment:
            queryset = queryset.filter(environment=environment)
        
        return queryset
    
    def _cache_service_info(self, service, instance):
        """Cache service information"""
        cache_key = f"service:{service.service_name}:{instance.instance_id}"
        cache_data = {
            'service_name': service.service_name,
            'service_type': service.service_type,
            'base_url': service.base_url,
            'instance_id': instance.instance_id,
            'host': instance.host,
            'port': instance.port,
            'protocol': instance.protocol,
            'status': instance.status,
            'last_heartbeat': instance.last_heartbeat.isoformat() if instance.last_heartbeat else None
        }
        
        self.redis_client.setex(
            cache_key,
            timedelta(minutes=30),
            json.dumps(cache_data, cls=DjangoJSONEncoder)
        )
    
    def _remove_from_cache(self, service_name, instance_id):
        """Remove service from cache"""
        cache_key = f"service:{service_name}:{instance_id}"
        self.redis_client.delete(cache_key)


class HealthCheckService:
    """Service for managing health checks"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 10
    
    def perform_health_check(self, service_instance):
        """Perform health check on a service instance"""
        try:
            start_time = timezone.now()
            
            # Build health check URL
            health_url = f"{service_instance.protocol}://{service_instance.host}:{service_instance.port}"
            if service_instance.service.health_check_url.startswith('/'):
                health_url += service_instance.service.health_check_url
            else:
                health_url += '/' + service_instance.service.health_check_url
            
            # Perform request
            response = self.session.get(health_url, timeout=service_instance.health_check_timeout)
            end_time = timezone.now()
            
            # Calculate response time
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Determine status
            if response.status_code == 200:
                status = 'success'
                error_message = ''
            else:
                status = 'failure'
                error_message = f"HTTP {response.status_code}"
            
            # Create health check record
            health_check = HealthCheck.objects.create(
                service_instance=service_instance,
                status=status,
                response_time_ms=response_time_ms,
                response_code=response.status_code,
                error_message=error_message,
                response_body=response.text[:1000],  # Limit response body
                metadata={
                    'url': health_url,
                    'user_agent': 'ServiceDiscovery/1.0'
                }
            )
            
            # Update instance status
            service_instance.last_health_check = timezone.now()
            service_instance.status = 'healthy' if status == 'success' else 'unhealthy'
            service_instance.save()
            
            return health_check
            
        except requests.exceptions.Timeout:
            return self._create_failed_health_check(service_instance, 'timeout', 'Request timeout')
        except requests.exceptions.ConnectionError:
            return self._create_failed_health_check(service_instance, 'error', 'Connection error')
        except Exception as e:
            return self._create_failed_health_check(service_instance, 'error', str(e))
    
    def _create_failed_health_check(self, service_instance, status, error_message):
        """Create a failed health check record"""
        health_check = HealthCheck.objects.create(
            service_instance=service_instance,
            status=status,
            response_time_ms=service_instance.health_check_timeout * 1000,
            response_code=None,
            error_message=error_message,
            response_body='',
            metadata={'error_type': status}
        )
        
        # Update instance status
        service_instance.last_health_check = timezone.now()
        service_instance.status = 'unhealthy'
        service_instance.save()
        
        return health_check
    
    def perform_bulk_health_checks(self):
        """Perform health checks on all active service instances"""
        instances = ServiceInstance.objects.filter(
            service__status='active'
        ).select_related('service')
        
        results = []
        for instance in instances:
            # Check if health check is due
            if (not instance.last_health_check or 
                timezone.now() - instance.last_health_check > timedelta(seconds=instance.health_check_interval)):
                health_check = self.perform_health_check(instance)
                results.append(health_check)
        
        return results
    
    def get_health_summary(self, service_name=None):
        """Get health summary for services"""
        queryset = ServiceInstance.objects.select_related('service')
        
        if service_name:
            queryset = queryset.filter(service__service_name=service_name)
        
        summary = {}
        for instance in queryset:
            service_name = instance.service.service_name
            if service_name not in summary:
                summary[service_name] = {
                    'total_instances': 0,
                    'healthy_instances': 0,
                    'unhealthy_instances': 0,
                    'maintenance_instances': 0,
                    'last_health_check': None,
                    'average_response_time': 0
                }
            
            summary[service_name]['total_instances'] += 1
            
            if instance.status == 'healthy':
                summary[service_name]['healthy_instances'] += 1
            elif instance.status == 'unhealthy':
                summary[service_name]['unhealthy_instances'] += 1
            elif instance.status == 'maintenance':
                summary[service_name]['maintenance_instances'] += 1
            
            if instance.last_health_check:
                if not summary[service_name]['last_health_check'] or instance.last_health_check > summary[service_name]['last_health_check']:
                    summary[service_name]['last_health_check'] = instance.last_health_check
        
        # Calculate average response times
        for service_name in summary:
            avg_response_time = HealthCheck.objects.filter(
                service_instance__service__service_name=service_name,
                status='success'
            ).aggregate(avg=Avg('response_time_ms'))['avg']
            
            summary[service_name]['average_response_time'] = avg_response_time or 0
        
        return summary


class ConfigurationService:
    """Service for managing configurations"""
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    
    def get_configuration(self, key, service_name=None, environment='production', default=None):
        """Get configuration value"""
        try:
            # Try cache first
            cache_key = f"config:{key}:{service_name or 'global'}:{environment}"
            cached_value = self.redis_client.get(cache_key)
            
            if cached_value:
                return json.loads(cached_value)
            
            # Get from database
            config = Configuration.objects.get(
                key=key,
                service_name=service_name or '',
                environment=environment
            )
            
            # Cache the value
            self.redis_client.setex(
                cache_key,
                timedelta(minutes=30),
                config.value
            )
            
            return config.value
            
        except Configuration.DoesNotExist:
            return default
    
    def set_configuration(self, key, value, service_name=None, environment='production', 
                         description='', is_sensitive=False, is_encrypted=False, expires_at=None):
        """Set configuration value"""
        try:
            config, created = Configuration.objects.get_or_create(
                key=key,
                service_name=service_name or '',
                environment=environment,
                defaults={
                    'value': value,
                    'description': description,
                    'is_sensitive': is_sensitive,
                    'is_encrypted': is_encrypted,
                    'expires_at': expires_at
                }
            )
            
            if not created:
                # Update existing configuration
                old_value = config.value
                config.previous_value = old_value
                config.value = value
                config.version += 1
                config.description = description
                config.is_sensitive = is_sensitive
                config.is_encrypted = is_encrypted
                config.expires_at = expires_at
                config.save()
                
                # Create history record
                ConfigurationHistory.objects.create(
                    configuration=config,
                    change_type='update',
                    old_value=old_value,
                    new_value=value
                )
            else:
                # Create history record for new configuration
                ConfigurationHistory.objects.create(
                    configuration=config,
                    change_type='create',
                    new_value=value
                )
            
            # Update cache
            cache_key = f"config:{key}:{service_name or 'global'}:{environment}"
            self.redis_client.setex(
                cache_key,
                timedelta(minutes=30),
                value
            )
            
            return config
            
        except Exception as e:
            raise Exception(f"Failed to set configuration: {str(e)}")
    
    def delete_configuration(self, key, service_name=None, environment='production'):
        """Delete configuration"""
        try:
            config = Configuration.objects.get(
                key=key,
                service_name=service_name or '',
                environment=environment
            )
            
            # Create history record
            ConfigurationHistory.objects.create(
                configuration=config,
                change_type='delete',
                old_value=config.value
            )
            
            # Remove from cache
            cache_key = f"config:{key}:{service_name or 'global'}:{environment}"
            self.redis_client.delete(cache_key)
            
            # Delete configuration
            config.delete()
            
            return True
            
        except Configuration.DoesNotExist:
            return False
    
    def get_configurations_for_service(self, service_name, environment='production'):
        """Get all configurations for a service"""
        configs = Configuration.objects.filter(
            service_name=service_name,
            environment=environment
        ).exclude(expires_at__lt=timezone.now())
        
        return {config.key: config.value for config in configs}
    
    def bulk_update_configurations(self, configurations, environment='production', 
                                 service_name=None, change_reason=''):
        """Bulk update configurations"""
        results = []
        
        for config_data in configurations:
            try:
                config = self.set_configuration(
                    key=config_data['key'],
                    value=config_data['value'],
                    service_name=service_name,
                    environment=environment,
                    description=config_data.get('description', ''),
                    is_sensitive=config_data.get('is_sensitive', False),
                    is_encrypted=config_data.get('is_encrypted', False),
                    expires_at=config_data.get('expires_at')
                )
                
                results.append({
                    'key': config.key,
                    'status': 'success',
                    'config_id': str(config.id)
                })
                
            except Exception as e:
                results.append({
                    'key': config_data.get('key', 'unknown'),
                    'status': 'error',
                    'error': str(e)
                })
        
        return results
    
    def search_configurations(self, key=None, config_type=None, service_name=None, 
                            environment=None, is_sensitive=None):
        """Search configurations"""
        queryset = Configuration.objects.all()
        
        if key:
            queryset = queryset.filter(key__icontains=key)
        if config_type:
            queryset = queryset.filter(config_type=config_type)
        if service_name:
            queryset = queryset.filter(service_name__icontains=service_name)
        if environment:
            queryset = queryset.filter(environment=environment)
        if is_sensitive is not None:
            queryset = queryset.filter(is_sensitive=is_sensitive)
        
        return queryset.exclude(expires_at__lt=timezone.now())


class ServiceMetricsService:
    """Service for managing service metrics"""
    
    def record_metrics(self, service_instance, metrics_data):
        """Record metrics for a service instance"""
        try:
            metrics = ServiceMetrics.objects.create(
                service_instance=service_instance,
                cpu_usage=metrics_data.get('cpu_usage'),
                memory_usage=metrics_data.get('memory_usage'),
                disk_usage=metrics_data.get('disk_usage'),
                network_io=metrics_data.get('network_io'),
                request_count=metrics_data.get('request_count', 0),
                error_count=metrics_data.get('error_count', 0),
                response_time_avg=metrics_data.get('response_time_avg'),
                response_time_p95=metrics_data.get('response_time_p95'),
                response_time_p99=metrics_data.get('response_time_p99'),
                custom_metrics=metrics_data.get('custom_metrics', {})
            )
            
            return metrics
            
        except Exception as e:
            raise Exception(f"Failed to record metrics: {str(e)}")
    
    def get_service_metrics(self, service_name, hours=24):
        """Get metrics for a service"""
        from datetime import datetime, timedelta
        
        start_time = timezone.now() - timedelta(hours=hours)
        
        metrics = ServiceMetrics.objects.filter(
            service_instance__service__service_name=service_name,
            recorded_at__gte=start_time
        ).select_related('service_instance')
        
        return metrics.order_by('recorded_at')
    
    def get_metrics_summary(self, service_name=None, hours=24):
        """Get metrics summary"""
        from datetime import datetime, timedelta
        
        start_time = timezone.now() - timedelta(hours=hours)
        
        queryset = ServiceMetrics.objects.filter(recorded_at__gte=start_time)
        
        if service_name:
            queryset = queryset.filter(service_instance__service__service_name=service_name)
        
        summary = queryset.aggregate(
            avg_cpu=Avg('cpu_usage'),
            avg_memory=Avg('memory_usage'),
            avg_disk=Avg('disk_usage'),
            avg_network=Avg('network_io'),
            total_requests=Sum('request_count'),
            total_errors=Sum('error_count'),
            avg_response_time=Avg('response_time_avg')
        )
        
        return summary


class ServiceDiscoveryStatsService:
    """Service for generating service discovery statistics"""
    
    def get_overall_stats(self):
        """Get overall service discovery statistics"""
        stats = {
            'total_services': ServiceRegistry.objects.count(),
            'active_services': ServiceRegistry.objects.filter(status='active').count(),
            'total_instances': ServiceInstance.objects.count(),
            'healthy_instances': ServiceInstance.objects.filter(status='healthy').count(),
            'total_configurations': Configuration.objects.count(),
            'services_by_type': {},
            'services_by_environment': {}
        }
        
        # Services by type
        type_stats = ServiceRegistry.objects.values('service_type').annotate(count=Count('id'))
        for stat in type_stats:
            stats['services_by_type'][stat['service_type']] = stat['count']
        
        # Services by environment
        env_stats = ServiceRegistry.objects.values('environment').annotate(count=Count('id'))
        for stat in env_stats:
            stats['services_by_environment'][stat['environment']] = stat['count']
        
        return stats
    
    def get_health_stats(self):
        """Get health statistics"""
        health_stats = {
            'total_health_checks': HealthCheck.objects.count(),
            'successful_health_checks': HealthCheck.objects.filter(status='success').count(),
            'failed_health_checks': HealthCheck.objects.filter(status='failure').count(),
            'timeout_health_checks': HealthCheck.objects.filter(status='timeout').count(),
            'average_response_time': HealthCheck.objects.filter(status='success').aggregate(avg=Avg('response_time_ms'))['avg'] or 0
        }
        
        return health_stats
