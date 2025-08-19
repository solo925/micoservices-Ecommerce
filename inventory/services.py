from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, F
from decimal import Decimal
from typing import List, Dict, Optional
import time
from .models import (
    InventoryItem, StockMovement, StockReservation, 
    StockAlert, Warehouse
)


class InventoryService:
    """Service class for inventory operations with optimized performance"""
    
    # Class-level cache for inventory statistics
    _stats_cache = {}
    _cache_ttl = 300  
    
    @classmethod
    def _get_cached_stats(cls, warehouse_id):
        """Get cached inventory statistics"""
        cache_key = f"inventory_stats:{warehouse_id or 'all'}"
        current_time = time.time()
        
        if cache_key in cls._stats_cache:
            cached_data = cls._stats_cache[cache_key]
            if current_time - cached_data['timestamp'] < cls._cache_ttl:
                return cached_data['stats']
            else:
                del cls._stats_cache[cache_key]
        
        return None
    
    @classmethod
    def _set_cached_stats(cls, warehouse_id, stats):
        """Cache inventory statistics"""
        cache_key = f"inventory_stats:{warehouse_id or 'all'}"
        cls._stats_cache[cache_key] = {
            'stats': stats,
            'timestamp': time.time()
        }
    
    @classmethod
    def clear_stats_cache(cls):
        """Clear the inventory statistics cache"""
        cls._stats_cache.clear()
    
    @staticmethod
    def adjust_stock(inventory_item: InventoryItem, adjustment_type: str, 
                    quantity: int, reason: str, performed_by: str = None,
                    unit_cost: Decimal = None) -> StockMovement:
        """
        Adjust stock levels for an inventory item with optimized database operations
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
            
            # Update inventory with optimized fields
            update_fields = ['quantity_available']
            inventory_item.quantity_available = new_quantity
            
            if unit_cost:
                inventory_item.last_cost = unit_cost
                inventory_item.unit_cost = unit_cost
                update_fields.extend(['last_cost', 'unit_cost'])
            
            if movement_type == 'IN':
                inventory_item.last_restocked_at = timezone.now()
                update_fields.append('last_restocked_at')
            elif movement_type == 'OUT':
                inventory_item.last_sold_at = timezone.now()
                inventory_item.quantity_sold += quantity
                update_fields.extend(['last_sold_at', 'quantity_sold'])
            
            inventory_item.save(update_fields=update_fields)
            
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
            
            # Clear stats cache
            InventoryService.clear_stats_cache()
            
            return movement
    
    @staticmethod
    def reserve_stock(inventory_item: InventoryItem, quantity: int,
                     reference_type: str, reference_id: str, reserved_by: str,
                     expires_at: timezone.datetime) -> StockReservation:
        """
        Reserve stock for an order or cart with optimized database operations
        """
        with transaction.atomic():
            if not inventory_item.can_reserve(quantity):
                raise ValueError(f"Insufficient stock. Available: {inventory_item.quantity_available}")
            
            # Update inventory quantities with optimized fields
            inventory_item.quantity_available -= quantity
            inventory_item.quantity_reserved += quantity
            inventory_item.save(update_fields=['quantity_available', 'quantity_reserved'])
            
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
            
            # Clear stats cache
            InventoryService.clear_stats_cache()
            
            return reservation
    
    @staticmethod
    def confirm_reservation(reservation: StockReservation) -> StockMovement:
        """
        Confirm a reservation (convert to sold) with optimized database operations
        """
        with transaction.atomic():
            if reservation.status != 'ACTIVE':
                raise ValueError("Reservation is not active")
            
            # Update reservation with optimized fields
            reservation.status = 'CONFIRMED'
            reservation.confirmed_at = timezone.now()
            reservation.save(update_fields=['status', 'confirmed_at'])
            
            # Update inventory with optimized fields
            inventory_item = reservation.inventory_item
            inventory_item.quantity_reserved -= reservation.quantity
            inventory_item.quantity_sold += reservation.quantity
            inventory_item.last_sold_at = timezone.now()
            inventory_item.save(update_fields=['quantity_reserved', 'quantity_sold', 'last_sold_at'])
            
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
            
            # Clear stats cache
            InventoryService.clear_stats_cache()
            
            return movement
    
    @staticmethod
    def release_reservation(reservation: StockReservation) -> StockMovement:
        """
        Release a reservation (return to available stock) with optimized database operations
        """
        with transaction.atomic():
            if reservation.status != 'ACTIVE':
                raise ValueError("Reservation is not active")
            
            # Update reservation with optimized fields
            reservation.status = 'RELEASED'
            reservation.released_at = timezone.now()
            reservation.save(update_fields=['status', 'released_at'])
            
            # Update inventory with optimized fields
            inventory_item = reservation.inventory_item
            inventory_item.quantity_reserved -= reservation.quantity
            inventory_item.quantity_available += reservation.quantity
            inventory_item.save(update_fields=['quantity_reserved', 'quantity_available'])
            
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
            
            # Clear stats cache
            InventoryService.clear_stats_cache()
            
            return movement
    
    @staticmethod
    def transfer_stock(from_item: InventoryItem, to_item: InventoryItem,
                      quantity: int, performed_by: str = None) -> tuple:
        """
        Transfer stock between inventory items (warehouses) with optimized database operations
        """
        with transaction.atomic():
            if from_item.quantity_available < quantity:
                raise ValueError(f"Insufficient stock in source. Available: {from_item.quantity_available}")
            
            # Update source inventory with optimized fields
            from_item.quantity_available -= quantity
            from_item.save(update_fields=['quantity_available'])
            
            # Update destination inventory with optimized fields
            to_item.quantity_available += quantity
            to_item.save(update_fields=['quantity_available'])
            
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
            
            # Clear stats cache
            InventoryService.clear_stats_cache()
            
            return out_movement, in_movement
    
    @staticmethod
    def bulk_update_stock(updates: List[Dict]) -> List[StockMovement]:
        """
        Bulk update stock levels with optimized database operations
        """
        movements = []
        inventory_updates = []
        
        with transaction.atomic():
            # Prepare bulk updates
            for update in updates:
                inventory_item = update['inventory_item']
                new_quantity = update['quantity']
                reason = update.get('reason', 'Bulk update')
                performed_by = update.get('performed_by')
                
                old_quantity = inventory_item.quantity_available
                inventory_item.quantity_available = new_quantity
                inventory_updates.append(inventory_item)
                
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
            
            # Bulk update inventory items
            if inventory_updates:
                InventoryItem.objects.bulk_update(inventory_updates, ['quantity_available'])
                
                # Check alerts for updated items
                for item in inventory_updates:
                    InventoryService._check_stock_alerts(item)
        
        # Clear stats cache
        InventoryService.clear_stats_cache()
        
        return movements
    
    @staticmethod
    def bulk_reserve_stock(reservations: List[Dict]) -> List[StockReservation]:
        """
        Bulk reserve stock with optimized database operations
        """
        created_reservations = []
        inventory_updates = []
        
        with transaction.atomic():
            for reservation_data in reservations:
                inventory_item = reservation_data['inventory_item']
                quantity = reservation_data['quantity']
                reference_type = reservation_data['reference_type']
                reference_id = reservation_data['reference_id']
                reserved_by = reservation_data['reserved_by']
                expires_at = reservation_data['expires_at']
                
                if not inventory_item.can_reserve(quantity):
                    raise ValueError(f"Insufficient stock for {inventory_item.sku}. Available: {inventory_item.quantity_available}")
                
                # Update inventory quantities
                inventory_item.quantity_available -= quantity
                inventory_item.quantity_reserved += quantity
                inventory_updates.append(inventory_item)
                
                # Create reservation
                reservation = StockReservation.objects.create(
                    inventory_item=inventory_item,
                    quantity=quantity,
                    reference_type=reference_type,
                    reference_id=reference_id,
                    reserved_by=reserved_by,
                    expires_at=expires_at
                )
                created_reservations.append(reservation)
                
                # Create movement record
                StockMovement.objects.create(
                    inventory_item=inventory_item,
                    movement_type='RESERVED',
                    quantity=quantity,
                    reference_type=reference_type,
                    reference_id=reference_id,
                    reason=f"Bulk reserved for {reference_type} {reference_id}",
                    performed_by=reserved_by,
                    quantity_before=inventory_item.quantity_available + quantity,
                    quantity_after=inventory_item.quantity_available
                )
            
            # Bulk update inventory items
            if inventory_updates:
                InventoryItem.objects.bulk_update(inventory_updates, ['quantity_available', 'quantity_reserved'])
        
        # Clear stats cache
        InventoryService.clear_stats_cache()
        
        return created_reservations
    
    @staticmethod
    def cleanup_expired_reservations():
        """
        Cleanup expired reservations with optimized database operations
        """
        # Use select_related to avoid N+1 queries
        expired_reservations = StockReservation.objects.filter(
            status='ACTIVE',
            expires_at__lt=timezone.now()
        ).select_related('inventory_item')
        
        # Prepare bulk updates
        inventory_updates = []
        reservation_updates = []
        movements_to_create = []
        alerts_to_create = []
        
        for reservation in expired_reservations:
            try:
                # Update reservation
                reservation.status = 'EXPIRED'
                reservation_updates.append(reservation)
                
                # Prepare inventory update
                inventory_item = reservation.inventory_item
                inventory_item.quantity_reserved -= reservation.quantity
                inventory_item.quantity_available += reservation.quantity
                inventory_updates.append(inventory_item)
                
                # Prepare movement record
                movements_to_create.append(StockMovement(
                    inventory_item=inventory_item,
                    movement_type='RELEASED',
                    quantity=reservation.quantity,
                    reference_type=reservation.reference_type,
                    reference_id=reservation.reference_id,
                    reason=f"Expired reservation {reservation.id}",
                    quantity_before=inventory_item.quantity_available - reservation.quantity,
                    quantity_after=inventory_item.quantity_available
                ))
                
                # Prepare alert
                alerts_to_create.append(StockAlert(
                    inventory_item=inventory_item,
                    alert_type='EXPIRED_RESERVATION',
                    message=f"Reservation {reservation.id} expired and was released",
                    current_quantity=inventory_item.quantity_available,
                ))
                
            except Exception as e:
                # Log error but continue with other reservations
                print(f"Error cleaning up reservation {reservation.id}: {e}")
        
        # Bulk operations
        if reservation_updates:
            StockReservation.objects.bulk_update(reservation_updates, ['status'])
        
        if inventory_updates:
            InventoryItem.objects.bulk_update(inventory_updates, ['quantity_available', 'quantity_reserved'])
        
        if movements_to_create:
            StockMovement.objects.bulk_create(movements_to_create)
        
        if alerts_to_create:
            StockAlert.objects.bulk_create(alerts_to_create)
        
        # Clear stats cache
        InventoryService.clear_stats_cache()
    
    @staticmethod
    def _check_stock_alerts(inventory_item: InventoryItem):
        """
        Check and create stock alerts if needed with optimized database operations
        """
        # Clear existing alerts for this item with optimized update
        StockAlert.objects.filter(
            inventory_item=inventory_item,
            status='ACTIVE'
        ).update(status='RESOLVED', resolved_at=timezone.now())
        
        alerts_to_create = []
        
        # Check for low stock
        if inventory_item.is_low_stock and not inventory_item.is_out_of_stock:
            alerts_to_create.append(StockAlert(
                inventory_item=inventory_item,
                alert_type='LOW_STOCK',
                message=f"Stock is low for {inventory_item.sku}. Current: {inventory_item.quantity_available}, Reorder level: {inventory_item.reorder_level}",
                current_quantity=inventory_item.quantity_available,
                threshold_quantity=inventory_item.reorder_level
            ))
        
        # Check for out of stock
        if inventory_item.is_out_of_stock:
            alerts_to_create.append(StockAlert(
                inventory_item=inventory_item,
                alert_type='OUT_OF_STOCK',
                message=f"Out of stock for {inventory_item.sku}",
                current_quantity=0,
                threshold_quantity=0
            ))
        
        # Check for overstock
        if (inventory_item.max_stock_level and 
            inventory_item.quantity_available > inventory_item.max_stock_level):
            alerts_to_create.append(StockAlert(
                inventory_item=inventory_item,
                alert_type='OVERSTOCK',
                message=f"Overstock for {inventory_item.sku}. Current: {inventory_item.quantity_available}, Max: {inventory_item.max_stock_level}",
                current_quantity=inventory_item.quantity_available,
                threshold_quantity=inventory_item.max_stock_level
            ))
        
        # Bulk create alerts if any
        if alerts_to_create:
            StockAlert.objects.bulk_create(alerts_to_create)
    
    @staticmethod
    def get_inventory_stats(warehouse_id: str = None) -> Dict:
        """
        Get inventory statistics with optimized queries and caching
        """
        # Check cache first
        cached_stats = InventoryService._get_cached_stats(warehouse_id)
        if cached_stats:
            return cached_stats
        
        # Build optimized query
        queryset = InventoryItem.objects.all()
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        
        # Use aggregation for better performance
        stats = queryset.aggregate(
            total_items=Count('id'),
            total_value=Sum(F('quantity_available') * F('unit_cost')),
            low_stock_items=Count('id', filter=Q(quantity_available__lte=F('reorder_level'))),
            out_of_stock_items=Count('id', filter=Q(quantity_available=0))
        )
        
        # Get additional stats with optimized queries
        total_reservations = StockReservation.objects.filter(
            inventory_item__in=queryset,
            status='ACTIVE'
        ).count()
        
        active_alerts = StockAlert.objects.filter(
            inventory_item__in=queryset,
            status='ACTIVE'
        ).count()
        
        warehouses_count = Warehouse.objects.filter(is_active=True).count()
        
        result = {
            'total_items': stats['total_items'] or 0,
            'total_value': float(stats['total_value'] or 0),
            'low_stock_items': stats['low_stock_items'] or 0,
            'out_of_stock_items': stats['out_of_stock_items'] or 0,
            'total_reservations': total_reservations,
            'active_alerts': active_alerts,
            'warehouses_count': warehouses_count
        }
        
        # Cache the result
        InventoryService._set_cached_stats(warehouse_id, result)
        
        return result
