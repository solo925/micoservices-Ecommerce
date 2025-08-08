from django.apps import AppConfig


class ServiceDiscoveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'service_discovery'
    verbose_name = 'Service Discovery & Configuration Management'

    def ready(self):
        import service_discovery.signals
