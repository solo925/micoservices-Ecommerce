from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    
    def ready(self):
        # Import signals when the app is ready
        try:
            import inventory.signals  # noqa
        except ImportError:
            pass