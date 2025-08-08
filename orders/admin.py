from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count
from .models import (
    Customer, Order, OrderItem, OrderHistory, ShippingMethod,
    Discount, Cart, CartItem
)
from django.utils import timezone


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone', 'total_orders', 'total_spent', 'created_at')
    list_filter = ('created_at', 'marketing_consent', 'newsletter_subscribed')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    readonly_fields = ('total_orders', 'total_spent', 'last_order_date', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user_id', 'email', 'first_name', 'last_name', 'phone', 'date_of_birth')
        }),
        ('Addresses', {
            'fields': ('default_shipping_address', 'default_billing_address')
        }),
        ('Preferences', {
            'fields': ('marketing_consent', 'newsletter_subscribed')
        }),
        ('Statistics', {
            'fields': ('total_orders', 'total_spent', 'last_order_date'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer_name', 'total_amount', 'status', 
                   'payment_status', 'fulfillment_status', 'created_at')
    list_filter = ('status', 'payment_status', 'fulfillment_status', 'created_at', 'shipping_method')
    search_fields = ('order_number', 'customer_name', 'customer_email', 'tracking_number')
    readonly_fields = ('order_number', 'created_at', 'updated_at', 'confirmed_at', 
                      'shipped_at', 'delivered_at', 'cancelled_at')
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'customer', 'customer_email', 'customer_name', 'customer_phone')
        }),
        ('Addresses', {
            'fields': ('shipping_address', 'billing_address')
        }),
        ('Pricing', {
            'fields': ('subtotal', 'tax_amount', 'shipping_amount', 'discount_amount', 'total_amount')
        }),
        ('Status', {
            'fields': ('status', 'payment_status', 'fulfillment_status')
        }),
        ('Payment', {
            'fields': ('payment_method', 'payment_transaction_id', 'payment_gateway')
        }),
        ('Shipping', {
            'fields': ('shipping_method', 'tracking_number', 'shipping_carrier', 'estimated_delivery')
        }),
        ('Notes', {
            'fields': ('notes', 'internal_notes', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at', 'cancelled_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product_name', 'product_sku', 'quantity', 'unit_price', 'total_price', 'is_fulfilled')
    list_filter = ('is_fulfilled', 'created_at')
    search_fields = ('product_name', 'product_sku', 'order__order_number')
    readonly_fields = ('total_price', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order', 'product_id', 'product_name', 'product_sku', 'product_variant')
        }),
        ('Pricing', {
            'fields': ('unit_price', 'quantity', 'total_price')
        }),
        ('Inventory', {
            'fields': ('inventory_item_id', 'reserved_quantity')
        }),
        ('Fulfillment', {
            'fields': ('is_fulfilled', 'fulfilled_quantity')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(OrderHistory)
class OrderHistoryAdmin(admin.ModelAdmin):
    list_display = ('order', 'event_type', 'description', 'user_name', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('order__order_number', 'description', 'user_name')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Event Information', {
            'fields': ('order', 'event_type', 'description')
        }),
        ('Changes', {
            'fields': ('old_value', 'new_value')
        }),
        ('User', {
            'fields': ('user_id', 'user_name')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'base_price', 'is_active', 'estimated_days_min', 'estimated_days_max')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description')
        }),
        ('Pricing', {
            'fields': ('base_price', 'price_per_kg')
        }),
        ('Delivery Time', {
            'fields': ('estimated_days_min', 'estimated_days_max')
        }),
        ('Restrictions', {
            'fields': ('is_active', 'min_order_amount', 'max_order_amount')
        }),
        ('Geographic Restrictions', {
            'fields': ('available_countries', 'excluded_countries')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'discount_type', 'discount_value', 'is_active', 'used_count', 'is_valid')
    list_filter = ('discount_type', 'is_active', 'valid_from', 'valid_until')
    search_fields = ('code', 'name', 'description')
    readonly_fields = ('used_count', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description')
        }),
        ('Discount Details', {
            'fields': ('discount_type', 'discount_value', 'max_discount_amount')
        }),
        ('Usage Restrictions', {
            'fields': ('min_order_amount', 'max_uses', 'used_count')
        }),
        ('Validity', {
            'fields': ('is_active', 'valid_from', 'valid_until')
        }),
        ('Product Restrictions', {
            'fields': ('applicable_products', 'excluded_products', 'customer_groups')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_valid(self, obj):
        return obj.is_valid
    is_valid.boolean = True
    is_valid.short_description = 'Valid'


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'item_count', 'total_amount', 'is_expired', 'created_at')
    list_filter = ('created_at', 'expires_at')
    search_fields = ('customer__email', 'customer__first_name', 'customer__last_name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Customer Information', {
            'fields': ('customer', 'session_id')
        }),
        ('Cart Details', {
            'fields': ('subtotal', 'tax_amount', 'shipping_amount', 'discount_amount', 'total_amount')
        }),
        ('Discount', {
            'fields': ('applied_discount',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'expires_at')
        }),
    )
    
    def item_count(self, obj):
        return obj.item_count
    item_count.short_description = 'Items'
    
    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True
    is_expired.short_description = 'Expired'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product_name', 'product_sku', 'quantity', 'unit_price', 'total_price')
    list_filter = ('created_at',)
    search_fields = ('product_name', 'product_sku', 'cart__customer__email')
    readonly_fields = ('total_price', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Cart Information', {
            'fields': ('cart',)
        }),
        ('Product Information', {
            'fields': ('product_id', 'product_name', 'product_sku', 'product_variant')
        }),
        ('Pricing', {
            'fields': ('unit_price', 'quantity', 'total_price')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# Custom admin actions
class OrderAdminWithActions(OrderAdmin):
    actions = ['mark_as_confirmed', 'mark_as_shipped', 'mark_as_delivered', 'mark_as_cancelled']
    
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status='confirmed', confirmed_at=timezone.now())
        self.message_user(request, f'{updated} orders marked as confirmed.')
    mark_as_confirmed.short_description = "Mark selected orders as confirmed"
    
    def mark_as_shipped(self, request, queryset):
        updated = queryset.update(status='shipped', shipped_at=timezone.now())
        self.message_user(request, f'{updated} orders marked as shipped.')
    mark_as_shipped.short_description = "Mark selected orders as shipped"
    
    def mark_as_delivered(self, request, queryset):
        updated = queryset.update(status='delivered', delivered_at=timezone.now())
        self.message_user(request, f'{updated} orders marked as delivered.')
    mark_as_delivered.short_description = "Mark selected orders as delivered"
    
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled', cancelled_at=timezone.now())
        self.message_user(request, f'{updated} orders marked as cancelled.')
    mark_as_cancelled.short_description = "Mark selected orders as cancelled"

# Re-register Order with actions
admin.site.unregister(Order)
admin.site.register(Order, OrderAdminWithActions)
