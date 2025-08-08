from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Warehouse, InventoryItem, StockMovement, StockReservation,
    StockAlert, InventoryAudit, InventoryAuditItem
)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'capacity', 'total_items', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code')
    readonly_fields = ('created_at', 'updated_at')
    
    def total_items(self, obj):
        return obj.inventory_items.count()
    total_items.short_description = 'Total Items'


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('sku', 'warehouse', 'quantity_available', 'quantity_reserved', 
                   'reorder_level', 'stock_status', 'last_restocked_at')
    list_filter = ('warehouse', 'last_restocked_at', 'created_at')
    search_fields = ('sku', 'product_id')
    readonly_fields = ('quantity_sold', 'last_sold_at', 'created_at', 'updated_at')
    
    def stock_status(self, obj):
        if obj.is_out_of_stock:
            return format_html('<span style="color: red;">Out of Stock</span>')
        elif obj.is_low_stock:
            return format_html('<span style="color: orange;">Low Stock</span>')
        else:
            return format_html('<span style="color: green;">In Stock</span>')
    stock_status.short_description = 'Status'


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('inventory_item', 'movement_type', 'quantity', 'reference_type', 
                   'reference_id', 'created_at')
    list_filter = ('movement_type', 'reference_type', 'created_at')
    search_fields = ('inventory_item__sku', 'reference_id', 'reason')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display = ('inventory_item', 'quantity', 'status', 'reference_type', 
                   'reference_id', 'reserved_at', 'expires_at')
    list_filter = ('status', 'reference_type', 'reserved_at', 'expires_at')
    search_fields = ('inventory_item__sku', 'reference_id')
    readonly_fields = ('reserved_at', 'confirmed_at', 'released_at')
    date_hierarchy = 'reserved_at'


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ('inventory_item', 'alert_type', 'status', 'current_quantity', 
                   'threshold_quantity', 'created_at')
    list_filter = ('alert_type', 'status', 'created_at')
    search_fields = ('inventory_item__sku', 'message')
    readonly_fields = ('created_at', 'updated_at')
    
    actions = ['acknowledge_alerts', 'resolve_alerts']
    
    def acknowledge_alerts(self, request, queryset):
        queryset.update(status='ACKNOWLEDGED')
    acknowledge_alerts.short_description = "Acknowledge selected alerts"
    
    def resolve_alerts(self, request, queryset):
        queryset.update(status='RESOLVED')
    resolve_alerts.short_description = "Resolve selected alerts"


@admin.register(InventoryAudit)
class InventoryAuditAdmin(admin.ModelAdmin):
    list_display = ('warehouse', 'audit_date', 'status', 'total_items_audited', 
                   'discrepancies_found', 'created_at')
    list_filter = ('status', 'audit_date', 'created_at')
    search_fields = ('warehouse__name', 'notes')
    readonly_fields = ('created_at', 'completed_at')


@admin.register(InventoryAuditItem)
class InventoryAuditItemAdmin(admin.ModelAdmin):
    list_display = ('audit', 'inventory_item', 'system_quantity', 'physical_quantity', 
                   'discrepancy', 'audited_at')
    list_filter = ('audit__audit_date', 'audited_at')
    search_fields = ('inventory_item__sku', 'audit__warehouse__name')
    readonly_fields = ('audited_at',)
    
    def has_discrepancy(self, obj):
        return obj.discrepancy != 0
    has_discrepancy.boolean = True
    has_discrepancy.short_description = 'Has Discrepancy'