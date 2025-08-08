from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import InventoryItem, StockAlert


@receiver(post_save, sender=InventoryItem)
def check_stock_alerts(sender, instance, created, **kwargs):
    """Check and create stock alerts when inventory is updated"""
    if not created:  # Only for updates, not new items
        # Clear existing active alerts for this item
        StockAlert.objects.filter(
            inventory_item=instance,
            status='ACTIVE'
        ).update(status='RESOLVED')
        
        # Check for low stock
        if instance.is_low_stock and not instance.is_out_of_stock:
            StockAlert.objects.create(
                inventory_item=instance,
                alert_type='LOW_STOCK',
                message=f"Stock is low for {instance.sku}. Current: {instance.quantity_available}, Reorder level: {instance.reorder_level}",
                current_quantity=instance.quantity_available,
                threshold_quantity=instance.reorder_level
            )
        
        # Check for out of stock
        if instance.is_out_of_stock:
            StockAlert.objects.create(
                inventory_item=instance,
                alert_type='OUT_OF_STOCK',
                message=f"Out of stock for {instance.sku}",
                current_quantity=0,
                threshold_quantity=0
            )
        
        # Check for overstock
        if (instance.max_stock_level and 
            instance.quantity_available > instance.max_stock_level):
            StockAlert.objects.create(
                inventory_item=instance,
                alert_type='OVERSTOCK',
                message=f"Overstock for {instance.sku}. Current: {instance.quantity_available}, Max: {instance.max_stock_level}",
                current_quantity=instance.quantity_available,
                threshold_quantity=instance.max_stock_level
            )
