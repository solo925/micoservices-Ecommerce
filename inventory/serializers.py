from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from .models import (
    Warehouse, InventoryItem, StockMovement, StockReservation,
    StockAlert, InventoryAudit, InventoryAuditItem
)


class WarehouseSerializer(serializers.ModelSerializer):
    """Serializer for Warehouse model"""
    total_items = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()
    
    class Meta:
        model = Warehouse
        fields = ('id', 'name', 'code', 'address', 'contact_info', 'is_active',
                 'capacity', 'total_items', 'total_value', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')
    
    def get_total_items(self, obj):
        return obj.inventory_items.count()
    
    def get_total_value(self, obj):
        total = sum(
            item.quantity_available * item.unit_cost 
            for item in obj.inventory_items.all()
        )
        return float(total)


class InventoryItemSerializer(serializers.ModelSerializer):
    """Serializer for InventoryItem model"""
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    total_quantity = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    total_value = serializers.SerializerMethodField()
    
    class Meta:
        model = InventoryItem
        fields = ('id', 'product_id', 'warehouse', 'warehouse_name', 'sku',
                 'quantity_available', 'quantity_reserved', 'quantity_sold',
                 'total_quantity', 'reorder_level', 'max_stock_level',
                 'unit_cost', 'last_cost', 'total_value', 'is_low_stock',
                 'is_out_of_stock', 'last_restocked_at', 'last_sold_at',
                 'created_at', 'updated_at')
        read_only_fields = ('id', 'quantity_sold', 'last_sold_at', 'created_at', 'updated_at')
    
    def get_total_value(self, obj):
        return float(obj.quantity_available * obj.unit_cost)
    
    def validate(self, attrs):
        if attrs.get('max_stock_level') and attrs.get('reorder_level'):
            if attrs['max_stock_level'] <= attrs['reorder_level']:
                raise serializers.ValidationError(
                    "Max stock level must be greater than reorder level"
                )
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    """Serializer for StockMovement model"""
    inventory_item_sku = serializers.CharField(source='inventory_item.sku', read_only=True)
    warehouse_name = serializers.CharField(source='inventory_item.warehouse.name', read_only=True)
    
    class Meta:
        model = StockMovement
        fields = ('id', 'inventory_item', 'inventory_item_sku', 'warehouse_name',
                 'movement_type', 'quantity', 'unit_cost', 'reference_type',
                 'reference_id', 'reason', 'notes', 'performed_by',
                 'quantity_before', 'quantity_after', 'created_at')
        read_only_fields = ('id', 'quantity_before', 'quantity_after', 'created_at')


class StockReservationSerializer(serializers.ModelSerializer):
    """Serializer for StockReservation model"""
    inventory_item_sku = serializers.CharField(source='inventory_item.sku', read_only=True)
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = StockReservation
        fields = ('id', 'inventory_item', 'inventory_item_sku', 'quantity',
                 'status', 'reference_type', 'reference_id', 'reserved_by',
                 'reserved_at', 'expires_at', 'confirmed_at', 'released_at',
                 'is_expired')
        read_only_fields = ('id', 'reserved_at', 'confirmed_at', 'released_at')


class StockAlertSerializer(serializers.ModelSerializer):
    """Serializer for StockAlert model"""
    inventory_item_sku = serializers.CharField(source='inventory_item.sku', read_only=True)
    warehouse_name = serializers.CharField(source='inventory_item.warehouse.name', read_only=True)
    
    class Meta:
        model = StockAlert
        fields = ('id', 'inventory_item', 'inventory_item_sku', 'warehouse_name',
                 'alert_type', 'status', 'message', 'current_quantity',
                 'threshold_quantity', 'acknowledged_by', 'acknowledged_at',
                 'resolved_at', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class InventoryAuditItemSerializer(serializers.ModelSerializer):
    """Serializer for InventoryAuditItem model"""
    inventory_item_sku = serializers.CharField(source='inventory_item.sku', read_only=True)
    has_discrepancy = serializers.ReadOnlyField()
    
    class Meta:
        model = InventoryAuditItem
        fields = ('id', 'inventory_item', 'inventory_item_sku', 'system_quantity',
                 'physical_quantity', 'discrepancy', 'has_discrepancy', 'notes',
                 'audited_at')
        read_only_fields = ('id', 'audited_at')
    
    def create(self, validated_data):
        # Calculate discrepancy
        physical = validated_data['physical_quantity']
        system = validated_data['system_quantity']
        validated_data['discrepancy'] = physical - system
        return super().create(validated_data)


class InventoryAuditSerializer(serializers.ModelSerializer):
    """Serializer for InventoryAudit model"""
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    items = InventoryAuditItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = InventoryAudit
        fields = ('id', 'warehouse', 'warehouse_name', 'audit_date', 'status',
                 'audited_by', 'notes', 'total_items_audited', 'discrepancies_found',
                 'items', 'created_at', 'completed_at')
        read_only_fields = ('id', 'total_items_audited', 'discrepancies_found',
                           'created_at', 'completed_at')


class StockAdjustmentSerializer(serializers.Serializer):
    """Serializer for stock adjustments"""
    inventory_item_id = serializers.UUIDField()
    adjustment_type = serializers.ChoiceField(choices=['increase', 'decrease', 'set'])
    quantity = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=500)
    unit_cost = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    
    def validate(self, attrs):
        inventory_item_id = attrs['inventory_item_id']
        adjustment_type = attrs['adjustment_type']
        quantity = attrs['quantity']
        
        try:
            inventory_item = InventoryItem.objects.get(id=inventory_item_id)
        except InventoryItem.DoesNotExist:
            raise serializers.ValidationError("Inventory item not found")
        
        if adjustment_type == 'decrease':
            if quantity > inventory_item.quantity_available:
                raise serializers.ValidationError(
                    f"Cannot decrease by {quantity}. Only {inventory_item.quantity_available} available."
                )
        
        attrs['inventory_item'] = inventory_item
        return attrs


class StockReservationCreateSerializer(serializers.Serializer):
    """Serializer for creating stock reservations"""
    inventory_item_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    reference_type = serializers.CharField(max_length=50, default='order')
    reference_id = serializers.UUIDField()
    expires_in_minutes = serializers.IntegerField(default=30, min_value=1, max_value=1440)  # Max 24 hours
    
    def validate(self, attrs):
        inventory_item_id = attrs['inventory_item_id']
        quantity = attrs['quantity']
        
        try:
            inventory_item = InventoryItem.objects.get(id=inventory_item_id)
        except InventoryItem.DoesNotExist:
            raise serializers.ValidationError("Inventory item not found")
        
        if not inventory_item.can_reserve(quantity):
            raise serializers.ValidationError(
                f"Cannot reserve {quantity} units. Only {inventory_item.quantity_available} available."
            )
        
        attrs['inventory_item'] = inventory_item
        attrs['expires_at'] = timezone.now() + timezone.timedelta(minutes=attrs['expires_in_minutes'])
        return attrs


class BulkStockUpdateSerializer(serializers.Serializer):
    """Serializer for bulk stock updates"""
    updates = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=100
    )
    
    def validate_updates(self, updates):
        validated_updates = []
        for update in updates:
            # Validate each update item
            inventory_item_id = update.get('inventory_item_id')
            quantity = update.get('quantity')
            
            if not inventory_item_id:
                raise serializers.ValidationError("inventory_item_id is required for each update")
            
            if quantity is None or quantity < 0:
                raise serializers.ValidationError("quantity must be a non-negative integer")
            
            try:
                inventory_item = InventoryItem.objects.get(id=inventory_item_id)
                update['inventory_item'] = inventory_item
                validated_updates.append(update)
            except InventoryItem.DoesNotExist:
                raise serializers.ValidationError(f"Inventory item {inventory_item_id} not found")
        
        return validated_updates


class InventoryReportSerializer(serializers.Serializer):
    """Serializer for inventory reports"""
    warehouse_id = serializers.UUIDField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    include_movements = serializers.BooleanField(default=False)
    include_reservations = serializers.BooleanField(default=False)
    include_alerts = serializers.BooleanField(default=False)
    low_stock_only = serializers.BooleanField(default=False)
    out_of_stock_only = serializers.BooleanField(default=False)


class InventoryStatsSerializer(serializers.Serializer):
    """Serializer for inventory statistics"""
    total_items = serializers.IntegerField()
    total_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    low_stock_items = serializers.IntegerField()
    out_of_stock_items = serializers.IntegerField()
    total_reservations = serializers.IntegerField()
    active_alerts = serializers.IntegerField()
    warehouses_count = serializers.IntegerField()
