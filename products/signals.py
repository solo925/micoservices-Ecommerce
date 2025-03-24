from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Product, Inventory

@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=Inventory)
def invalidate_product_cache(sender, instance, **kwargs):
    cache.delete_many([
        'all_products',
        f'product_{instance.id}'
    ])
