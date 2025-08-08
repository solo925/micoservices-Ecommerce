from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Optional
from .models import (
    InventoryItem, StockMovement, StockReservation, 
    StockAlert, Warehouse
)


class InventoryService:
    """Service class for inventory operations"""
    
    @staticmethod
    def adjust_stock(inventory_item: InventoryItem, adjustment_type: str, 
                    quantity: int, reason: str, performed_by: str = None,
                    unit_cost: Decimal = None) -> StockMovement:
        """
        Adjust stock levels for an inventory item
        """
        with transaction.atomic():
            old_quantity = inventory_item.quantity_available
            
            if adjustment_type == 'increase':
                new_quantity = old_quantity + quantity
                movement_type = 'IN'
            elif adjustment_type == 'decrease':
                new_quantity = max(0, old_quantity - quantity)
                movement_type = 'OUT'
            elif adjustment_type == 'set':
                new_quantity = quantity
                movement_type = 'ADJUSTMENT'
            else:
                raise ValueError("Invalid adjustment type")
            
            # Update inventory
            inventory_item.quantity_available = new_quantity
            if unit_cost:
                inventory_item.last_cost = unit_cost
                inventory_item.unit_cost = unit_cost
            
            if movement_type == 'IN':
                inventory_item.last_restocked_at = timezone.now()
            elif movement_type == 'OUT':
                inventory_item.last_sold_at = timezone.now()
                inventory_item.quantity_sold += quantity
            
            inventory_item.save()
            
            # Create movement record
            movement = StockMovement.objects.create(
                inventory_item=inventory_item,
                movement_type=movement_type,
                quantity=quantity,
                unit_cost=unit_cost,
                reason=reason,
                performed_by=performed_by,
                quantity_before=old_quantity,
                quantity_after=new_quantity
            )
            
            # Check for alerts
            InventoryService._check_stock_alerts(inventory_item)
            
            return movement
    
    @staticmethod
    def reserve_stock(inventory_item: InventoryItem, quantity: int,
                     reference_type: str, reference_id: str, reserved_by: str,
                     expires_at: timezone.datetime) -> StockReservation:
        """
        Reserve stock for an order or cart
        """
        with transaction.atomic():
            if not inventory_item.can_reserve(quantity):
                raise ValueError(f"Insufficient stock. Available: {inventory_item.quantity_available}")
            
            # Update inventory quantities
            inventory_item.quantity_available -= quantity
            inventory_item.quantity_reserved += quantity
            inventory_item.save()
            
            # Create reservation
            reservation = StockReservation.objects.create(
                inventory_item=inventory_item,
                quantity=quantity,
                reference_type=reference_type,
                reference_id=reference_id,
                reserved_by=reserved_by,
                expires_at=expires_at
            )
            
            # Create movement record
            StockMovement.objects.create(
                inventory_item=inventory_item,
                movement_type='RESERVED',
                quantity=quantity,
                reference_type=reference_type,
                reference_id=reference_id,
                reason=f"Reserved for {reference_type} {reference_id}",
                performed_by=reserved_by,
                quantity_before=inventory_item.quantity_available + quantity,
                quantity_after=inventory_item.quantity_available
            )
            
            return reservation
    
    @staticmethod
    def confirm_reservation(reservation: StockReservation) -> StockMovement:
        """
        Confirm a reservation (convert to sold)
        """
        with transaction.atomic():
            if reservation.status != 'ACTIVE':
                raise ValueError("Reservation is not active")
            
            # Update reservation
            reservation.status = 'CONFIRMED'
            reservation.confirmed_at = timezone.now()
            reservation.save()
            
            # Update inventory
            inventory_item = reservation.inventory_item
            inventory_item.quantity_reserved -= reservation.quantity
            inventory_item.quantity_sold += reservation.quantity
            inventory_item.last_sold_at = timezone.now()
            inventory_item.save()
            
            # Create movement record
            movement = StockMovement.objects.create(
                inventory_item=inventory_item,
                movement_type='OUT',
                quantity=reservation.quantity,
                reference_type=reservation.reference_type,
                reference_id=reservation.reference_id,
                reason=f"Confirmed reservation {reservation.id}",
                performed_by=reservation.reserved_by,
                quantity_before=inventory_item.quantity_reserved + reservation.quantity,
                quantity_after=inventory_item.quantity_reserved
            )
            
            # Check for alerts
            InventoryService._check_stock_alerts(inventory_item)
            
            return movement
    
    @staticmethod
    def release_reservation(reservation: StockReservation) -> StockMovement:
        """
        Release a reservation (return to available stock)
        """
        with transaction.atomic():
            if reservation.status != 'ACTIVE':
                raise ValueError("Reservation is not active")
            
            # Update reservation
            reservation.status = 'RELEASED'
            reservation.released_at = timezone.now()
            reservation.save()
            
            # Update inventory
            inventory_item = reservation.inventory_item
            inventory_item.quantity_reserved -= reservation.quantity
            inventory_item.quantity_available += reservation.quantity
            inventory_item.save()
            
            # Create movement record
            movement = StockMovement.objects.create(
                inventory_item=inventory_item,
                movement_type='RELEASED',
                quantity=reservation.quantity,
                reference_type=reservation.reference_type,
                reference_id=reservation.reference_id,
                reason=f"Released reservation {reservation.id}",
                performed_by=reservation.reserved_by,
                quantity_before=inventory_item.quantity_available - reservation.quantity,
                quantity_after=inventory_item.quantity_available
            )
            
            return movement
    
    @staticmethod
    def transfer_stock(from_item: InventoryItem, to_item: InventoryItem,
                      quantity: int, performed_by: str = None) -> tuple:
        """
        Transfer stock between inventory items (warehouses)
        """
        with transaction.atomic():
            if from_item.quantity_available < quantity:
                raise ValueError(f"Insufficient stock in source. Available: {from_item.quantity_available}")
            
            # Update source inventory
            from_item.quantity_available -= quantity
            from_item.save()
            
            # Update destination inventory
            to_item.quantity_available += quantity
            to_item.save()
            
            # Create movement records
            out_movement = StockMovement.objects.create(
                inventory_item=from_item,
                movement_type='TRANSFER',
                quantity=quantity,
                reason=f"Transfer to {to_item.warehouse.name}",
                performed_by=performed_by,
                quantity_before=from_item.quantity_available + quantity,
                quantity_after=from_item.quantity_available
            )
            
            in_movement = StockMovement.objects.create(
                inventory_item=to_item,
                movement_type='TRANSFER',
                quantity=quantity,
                reason=f"Transfer from {from_item.warehouse.name}",
                performed_by=performed_by,
                quantity_before=to_item.quantity_available - quantity,
                quantity_after=to_item.quantity_available
            )
            
            # Check alerts for both items
            InventoryService._check_stock_alerts(from_item)
            InventoryService._check_stock_alerts(to_item)
            
            return out_movement, in_movement
    
    @staticmethod
    def bulk_update_stock(updates: List[Dict]) -> List[StockMovement]:
        """
        Bulk update stock levels
        """
        movements = []
        with transaction.atomic():
            for update in updates:
                inventory_item = update['inventory_item']
                new_quantity = update['quantity']
                reason = update.get('reason', 'Bulk update')
                performed_by = update.get('performed_by')
                
                old_quantity = inventory_item.quantity_available
                inventory_item.quantity_available = new_quantity
                inventory_item.save()
                
                movement = StockMovement.objects.create(
                    inventory_item=inventory_item,
                    movement_type='ADJUSTMENT',
                    quantity=abs(new_quantity - old_quantity),
                    reason=reason,
                    performed_by=performed_by,
                    quantity_before=old_quantity,
                    quantity_after=new_quantity
                )
                movements.append(movement)
                
                # Check alerts
                InventoryService._check_stock_alerts(inventory_item)
        
        return movements
    
    @staticmethod
    def cleanup_expired_reservations():
        """
        Cleanup expired reservations (scheduled task)
        """
        expired_reservations = StockReservation.objects.filter(
            status='ACTIVE',
            expires_at__lt=timezone.now()
        )
        
        for reservation in expired_reservations:
            try:
                with transaction.atomic():
                    reservation.status = 'EXPIRED'
                    reservation.save()
                    
                    # Return stock to available
                    inventory_item = reservation.inventory_item
                    inventory_item.quantity_reserved -= reservation.quantity
                    inventory_item.quantity_available += reservation.quantity
                    inventory_item.save()
                    
                    # Create movement record
                    StockMovement.objects.create(
                        inventory_item=inventory_item,
                        movement_type='RELEASED',
                        quantity=reservation.quantity,
                        reference_type=reservation.reference_type,
                        reference_id=reservation.reference_id,
                        reason=f"Expired reservation {reservation.id}",
                        quantity_before=inventory_item.quantity_available - reservation.quantity,
                        quantity_after=inventory_item.quantity_available
                    )
                    
                    # Create alert for expired reservation
                    StockAlert.objects.create(
                        inventory_item=inventory_item,
                        alert_type='EXPIRED_RESERVATION',
                        message=f"Reservation {reservation.id} expired and was released",
                        current_quantity=inventory_item.quantity_available,
                    )
            except Exception as e:
                # Log error but continue with other reservations
                print(f"Error cleaning up reservation {reservation.id}: {e}")
    
    @staticmethod
    def _check_stock_alerts(inventory_item: InventoryItem):
        """
        Check and create stock alerts if needed
        """
        # Clear existing alerts for this item
        StockAlert.objects.filter(
            inventory_item=inventory_item,
            status='ACTIVE'
        ).update(status='RESOLVED', resolved_at=timezone.now())
        
        # Check for low stock
        if inventory_item.is_low_stock and not inventory_item.is_out_of_stock:
            StockAlert.objects.create(
                inventory_item=inventory_item,
                alert_type='LOW_STOCK',
                message=f"Stock is low for {inventory_item.sku}. Current: {inventory_item.quantity_available}, Reorder level: {inventory_item.reorder_level}",
                current_quantity=inventory_item.quantity_available,
                threshold_quantity=inventory_item.reorder_level
            )
        
        # Check for out of stock
        if inventory_item.is_out_of_stock:
            StockAlert.objects.create(
                inventory_item=inventory_item,
                alert_type='OUT_OF_STOCK',
                message=f"Out of stock for {inventory_item.sku}",
                current_quantity=0,
                threshold_quantity=0
            )
        
        # Check for overstock
        if (inventory_item.max_stock_level and 
            inventory_item.quantity_available > inventory_item.max_stock_level):
            StockAlert.objects.create(
                inventory_item=inventory_item,
                alert_type='OVERSTOCK',
                message=f"Overstock for {inventory_item.sku}. Current: {inventory_item.quantity_available}, Max: {inventory_item.max_stock_level}",
                current_quantity=inventory_item.quantity_available,
                threshold_quantity=inventory_item.max_stock_level
            )
    
    @staticmethod
    def get_inventory_stats(warehouse_id: str = None) -> Dict:
        """
        Get inventory statistics
        """
        queryset = InventoryItem.objects.all()
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        
        total_items = queryset.count()
        total_value = sum(
            item.quantity_available * item.unit_cost 
            for item in queryset
        )
        
        from django.db.models import F
        low_stock_items = queryset.filter(
            quantity_available__lte=F('reorder_level')
        ).count()
        
        out_of_stock_items = queryset.filter(quantity_available=0).count()
        
        total_reservations = StockReservation.objects.filter(
            inventory_item__in=queryset,
            status='ACTIVE'
        ).count()
        
        active_alerts = StockAlert.objects.filter(
            inventory_item__in=queryset,
            status='ACTIVE'
        ).count()
        
        warehouses_count = Warehouse.objects.filter(is_active=True).count()
        
        return {
            'total_items': total_items,
            'total_value': total_value,
            'low_stock_items': low_stock_items,
            'out_of_stock_items': out_of_stock_items,
            'total_reservations': total_reservations,
            'active_alerts': active_alerts,
            'warehouses_count': warehouses_count
        }
