import uuid
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal


class Warehouse(models.Model):
    """Warehouse model for inventory management"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    address = models.JSONField(default=dict)
    contact_info = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    capacity = models.IntegerField(validators=[MinValueValidator(0)], help_text="Maximum capacity")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'warehouses'
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['code']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class InventoryItem(models.Model):
    """Inventory tracking for products in warehouses"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product_id = models.UUIDField(db_index=True)  # Reference to Product service
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='inventory_items')
    sku = models.CharField(max_length=100, db_index=True)
    
    # Stock levels
    quantity_available = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    quantity_reserved = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    quantity_sold = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Thresholds
    reorder_level = models.IntegerField(default=10, validators=[MinValueValidator(0)])
    max_stock_level = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    
    # Cost tracking
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    last_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Dates
    last_restocked_at = models.DateTimeField(null=True, blank=True)
    last_sold_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'inventory_items'
        unique_together = ('product_id', 'warehouse')
        indexes = [
            models.Index(fields=['product_id']),
            models.Index(fields=['sku']),
            models.Index(fields=['quantity_available']),
            models.Index(fields=['reorder_level']),
        ]
    
    def __str__(self):
        return f"{self.sku} - {self.warehouse.name}"
    
    @property
    def total_quantity(self):
        """Total quantity including available and reserved"""
        return self.quantity_available + self.quantity_reserved
    
    @property
    def is_low_stock(self):
        """Check if stock is below reorder level"""
        return self.quantity_available <= self.reorder_level
    
    @property
    def is_out_of_stock(self):
        """Check if completely out of stock"""
        return self.quantity_available == 0
    
    def can_reserve(self, quantity):
        """Check if we can reserve the requested quantity"""
        return self.quantity_available >= quantity


class StockMovement(models.Model):
    """Track all stock movements for audit and reporting"""
    MOVEMENT_TYPES = (
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
        ('RESERVED', 'Reserved'),
        ('RELEASED', 'Released'),
        ('ADJUSTMENT', 'Adjustment'),
        ('TRANSFER', 'Transfer'),
        ('DAMAGED', 'Damaged'),
        ('EXPIRED', 'Expired'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # References
    reference_type = models.CharField(max_length=50, blank=True)  
    reference_id = models.UUIDField(null=True, blank=True, db_index=True)
    
    # Details
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    performed_by = models.UUIDField(null=True, blank=True, db_index=True)  
    
    # Snapshots for audit
    quantity_before = models.IntegerField()
    quantity_after = models.IntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'stock_movements'
        indexes = [
            models.Index(fields=['movement_type']),
            models.Index(fields=['reference_type', 'reference_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['performed_by']),
        ]
    
    def __str__(self):
        return f"{self.movement_type} - {self.quantity} units - {self.inventory_item.sku}"


class StockReservation(models.Model):
    """Track stock reservations for orders"""
    RESERVATION_STATUS = (
        ('ACTIVE', 'Active'),
        ('CONFIRMED', 'Confirmed'),
        ('RELEASED', 'Released'),
        ('EXPIRED', 'Expired'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='reservations')
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=RESERVATION_STATUS, default='ACTIVE')
    
    # References
    reference_type = models.CharField(max_length=50, default='order')
    reference_id = models.UUIDField(db_index=True)  
    reserved_by = models.UUIDField(db_index=True)  
    
    # Timing
    reserved_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'stock_reservations'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['reference_type', 'reference_id']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['reserved_by']),
        ]
    
    def __str__(self):
        return f"Reservation {self.id} - {self.quantity} units"
    
    @property
    def is_expired(self):
        """Check if reservation has expired"""
        return timezone.now() > self.expires_at and self.status == 'ACTIVE'
    
    def release(self):
        """Release the reservation"""
        if self.status == 'ACTIVE':
            self.status = 'RELEASED'
            self.released_at = timezone.now()
            self.save()
            
            # Update inventory
            self.inventory_item.quantity_reserved -= self.quantity
            self.inventory_item.quantity_available += self.quantity
            self.inventory_item.save()
            
            # Create movement record
            StockMovement.objects.create(
                inventory_item=self.inventory_item,
                movement_type='RELEASED',
                quantity=self.quantity,
                reference_type=self.reference_type,
                reference_id=self.reference_id,
                reason=f"Released reservation {self.id}",
                quantity_before=self.inventory_item.quantity_available - self.quantity,
                quantity_after=self.inventory_item.quantity_available
            )


class StockAlert(models.Model):
    """Stock alerts for low inventory, out of stock, etc."""
    ALERT_TYPES = (
        ('LOW_STOCK', 'Low Stock'),
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('OVERSTOCK', 'Overstock'),
        ('EXPIRED_RESERVATION', 'Expired Reservation'),
    )
    
    ALERT_STATUS = (
        ('ACTIVE', 'Active'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('RESOLVED', 'Resolved'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    status = models.CharField(max_length=20, choices=ALERT_STATUS, default='ACTIVE')
    message = models.TextField()
    current_quantity = models.IntegerField()
    threshold_quantity = models.IntegerField(null=True, blank=True)
    
    # Actions
    acknowledged_by = models.UUIDField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'stock_alerts'
        indexes = [
            models.Index(fields=['alert_type']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.alert_type} - {self.inventory_item.sku}"


class InventoryAudit(models.Model):
    """Periodic inventory audits"""
    AUDIT_STATUS = (
        ('PLANNED', 'Planned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='audits')
    audit_date = models.DateField()
    status = models.CharField(max_length=20, choices=AUDIT_STATUS, default='PLANNED')
    
    # Audit details
    audited_by = models.UUIDField(db_index=True)  
    notes = models.TextField(blank=True)
    total_items_audited = models.IntegerField(default=0)
    discrepancies_found = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'inventory_audits'
        indexes = [
            models.Index(fields=['audit_date']),
            models.Index(fields=['status']),
            models.Index(fields=['audited_by']),
        ]
    
    def __str__(self):
        return f"Audit {self.warehouse.name} - {self.audit_date}"


class InventoryAuditItem(models.Model):
    """Individual items in an inventory audit"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit = models.ForeignKey(InventoryAudit, on_delete=models.CASCADE, related_name='items')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    
    # Audit results
    system_quantity = models.IntegerField()
    physical_quantity = models.IntegerField()
    discrepancy = models.IntegerField() 
    
    notes = models.TextField(blank=True)
    audited_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'inventory_audit_items'
        unique_together = ('audit', 'inventory_item')
    
    def __str__(self):
        return f"Audit Item {self.inventory_item.sku} - Discrepancy: {self.discrepancy}"
    
    @property
    def has_discrepancy(self):
        """Check if there's a discrepancy between system and physical count"""
        return self.discrepancy != 0