from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import ServiceInstance, HealthCheck, Configuration, ServiceMetrics
from .services import HealthCheckService, ServiceMetricsService


@receiver(post_save, sender=ServiceInstance)
def update_service_heartbeat(sender, instance, created, **kwargs):
    """Update service heartbeat when instance is saved"""
    if created:
        # Update the service's last heartbeat
        service = instance.service
        service.last_heartbeat = timezone.now()
        service.save()


@receiver(post_save, sender=HealthCheck)
def update_instance_status(sender, instance, created, **kwargs):
    """Update instance status based on health check results"""
    if created:
        service_instance = instance.service_instance
        
        # Update instance status based on health check result
        if instance.status == 'success':
            service_instance.status = 'healthy'
        else:
            service_instance.status = 'unhealthy'
        
        service_instance.last_health_check = instance.checked_at
        service_instance.save()


@receiver(post_save, sender=Configuration)
def clear_config_cache(sender, instance, created, **kwargs):
    """Clear configuration cache when configuration is updated"""
    from django.core.cache import cache
    
    # Clear cache for this configuration
    cache_key = f"config:{instance.key}:{instance.service_name or 'global'}:{instance.environment}"
    cache.delete(cache_key)


@receiver(post_delete, sender=ServiceInstance)
def cleanup_service_registry(sender, instance, **kwargs):
    """Clean up service registry when instance is deleted"""
    service = instance.service
    
    # If no more instances exist, mark service as inactive
    if not service.instances.exists():
        service.status = 'inactive'
        service.save()


@receiver(post_delete, sender=HealthCheck)
def cleanup_old_health_checks(sender, instance, **kwargs):
    """Clean up old health checks"""
    # This could trigger additional cleanup logic
    pass


# Utility functions for external use
def trigger_health_check(instance_id):
    """Trigger health check for a specific instance"""
    try:
        instance = ServiceInstance.objects.get(instance_id=instance_id)
        health_service = HealthCheckService()
        return health_service.perform_health_check(instance)
    except ServiceInstance.DoesNotExist:
        return None


def record_service_metrics(instance_id, metrics_data):
    """Record metrics for a service instance"""
    try:
        instance = ServiceInstance.objects.get(instance_id=instance_id)
        metrics_service = ServiceMetricsService()
        return metrics_service.record_metrics(instance, metrics_data)
    except ServiceInstance.DoesNotExist:
        return None


def perform_bulk_health_checks():
    """Perform health checks on all active services"""
    health_service = HealthCheckService()
    return health_service.perform_bulk_health_checks()


def cleanup_old_data():
    """Clean up old health checks, metrics, and history"""
    from datetime import timedelta
    
    # Clean up old health checks (older than 30 days)
    cutoff_date = timezone.now() - timedelta(days=30)
    HealthCheck.objects.filter(checked_at__lt=cutoff_date).delete()
    
    # Clean up old metrics (older than 30 days)
    ServiceMetrics.objects.filter(recorded_at__lt=cutoff_date).delete()
    
    # Clean up old configuration history (older than 90 days)
    from .models import ConfigurationHistory
    history_cutoff = timezone.now() - timedelta(days=90)
    ConfigurationHistory.objects.filter(changed_at__lt=history_cutoff).delete()
