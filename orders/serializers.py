from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from .models import (
    Customer, Order, OrderItem, OrderHistory, ShippingMethod,
    Discount, Cart, CartItem
)


class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for Customer model"""
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = Customer
        fields = ('id', 'user_id', 'email', 'first_name', 'last_name', 'full_name',
                 'phone', 'date_of_birth', 'default_shipping_address', 'default_billing_address',
                 'marketing_consent', 'newsletter_subscribed', 'total_orders', 'total_spent',
                 'last_order_date', 'created_at', 'updated_at')
        read_only_fields = ('id', 'total_orders', 'total_spent', 'last_order_date',
                           'created_at', 'updated_at')


class CustomerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating customers"""
    class Meta:
        model = Customer
        fields = ('email', 'first_name', 'last_name', 'phone', 'date_of_birth',
                 'default_shipping_address', 'default_billing_address',
                 'marketing_consent', 'newsletter_subscribed')


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for OrderItem model"""
    class Meta:
        model = OrderItem
        fields = ('id', 'product_id', 'product_name', 'product_sku', 'product_variant',
                 'unit_price', 'quantity', 'total_price', 'inventory_item_id',
                 'reserved_quantity', 'is_fulfilled', 'fulfilled_quantity',
                 'created_at', 'updated_at')
        read_only_fields = ('id', 'total_price', 'created_at', 'updated_at')


class OrderHistorySerializer(serializers.ModelSerializer):
    """Serializer for OrderHistory model"""
    class Meta:
        model = OrderHistory
        fields = ('id', 'event_type', 'description', 'old_value', 'new_value',
                 'user_id', 'user_name', 'created_at')
        read_only_fields = ('id', 'created_at')


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order model"""
    items = OrderItemSerializer(many=True, read_only=True)
    history = OrderHistorySerializer(many=True, read_only=True)
    is_paid = serializers.ReadOnlyField()
    is_fulfilled = serializers.ReadOnlyField()
    can_cancel = serializers.ReadOnlyField()
    can_refund = serializers.ReadOnlyField()
    
    class Meta:
        model = Order
        fields = ('id', 'order_number', 'customer', 'customer_email', 'customer_name',
                 'customer_phone', 'shipping_address', 'billing_address', 'subtotal',
                 'tax_amount', 'shipping_amount', 'discount_amount', 'total_amount',
                 'status', 'payment_status', 'fulfillment_status', 'payment_method',
                 'payment_transaction_id', 'payment_gateway', 'shipping_method',
                 'tracking_number', 'shipping_carrier', 'estimated_delivery',
                 'notes', 'internal_notes', 'metadata', 'is_paid', 'is_fulfilled',
                 'can_cancel', 'can_refund', 'items', 'history', 'created_at',
                 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at', 'cancelled_at')
        read_only_fields = ('id', 'order_number', 'created_at', 'updated_at',
                           'confirmed_at', 'shipped_at', 'delivered_at', 'cancelled_at')


class OrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating orders"""
    items = serializers.ListField(child=serializers.DictField(), write_only=True)
    
    class Meta:
        model = Order
        fields = ('customer', 'customer_email', 'customer_name', 'customer_phone',
                 'shipping_address', 'billing_address', 'shipping_method',
                 'payment_method', 'notes', 'items')
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # Calculate totals
        subtotal = Decimal('0.00')
        for item_data in items_data:
            unit_price = Decimal(str(item_data['unit_price']))
            quantity = item_data['quantity']
            subtotal += unit_price * quantity
        
        # Set default values
        validated_data['subtotal'] = subtotal
        validated_data['total_amount'] = subtotal  # Will be updated with tax/shipping
        
        order = Order.objects.create(**validated_data)
        
        # Create order items
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        
        # Create order history
        OrderHistory.objects.create(
            order=order,
            event_type='created',
            description='Order created',
            user_id=self.context.get('user_id'),
            user_name=self.context.get('user_name', 'System')
        )
        
        return order


class OrderUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating orders"""
    class Meta:
        model = Order
        fields = ('status', 'payment_status', 'fulfillment_status', 'tracking_number',
                 'shipping_carrier', 'estimated_delivery', 'notes', 'internal_notes')
    
    def update(self, instance, validated_data):
        old_status = instance.status
        old_payment_status = instance.payment_status
        
        order = super().update(instance, validated_data)
        
        # Create history entries for status changes
        if 'status' in validated_data and validated_data['status'] != old_status:
            OrderHistory.objects.create(
                order=order,
                event_type='status_changed',
                description=f'Order status changed from {old_status} to {validated_data["status"]}',
                old_value=old_status,
                new_value=validated_data['status'],
                user_id=self.context.get('user_id'),
                user_name=self.context.get('user_name', 'System')
            )
        
        if 'payment_status' in validated_data and validated_data['payment_status'] != old_payment_status:
            OrderHistory.objects.create(
                order=order,
                event_type='payment_received' if validated_data['payment_status'] == 'paid' else 'status_changed',
                description=f'Payment status changed from {old_payment_status} to {validated_data["payment_status"]}',
                old_value=old_payment_status,
                new_value=validated_data['payment_status'],
                user_id=self.context.get('user_id'),
                user_name=self.context.get('user_name', 'System')
            )
        
        return order


class ShippingMethodSerializer(serializers.ModelSerializer):
    """Serializer for ShippingMethod model"""
    class Meta:
        model = ShippingMethod
        fields = ('id', 'name', 'code', 'description', 'base_price', 'price_per_kg',
                 'estimated_days_min', 'estimated_days_max', 'is_active',
                 'min_order_amount', 'max_order_amount', 'available_countries',
                 'excluded_countries', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class DiscountSerializer(serializers.ModelSerializer):
    """Serializer for Discount model"""
    is_valid = serializers.ReadOnlyField()
    
    class Meta:
        model = Discount
        fields = ('id', 'code', 'name', 'description', 'discount_type', 'discount_value',
                 'max_discount_amount', 'min_order_amount', 'max_uses', 'used_count',
                 'is_active', 'valid_from', 'valid_until', 'applicable_products',
                 'excluded_products', 'customer_groups', 'is_valid', 'created_at', 'updated_at')
        read_only_fields = ('id', 'used_count', 'created_at', 'updated_at')


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for CartItem model"""
    class Meta:
        model = CartItem
        fields = ('id', 'product_id', 'product_name', 'product_sku', 'product_variant',
                 'unit_price', 'quantity', 'total_price', 'created_at', 'updated_at')
        read_only_fields = ('id', 'total_price', 'created_at', 'updated_at')


class CartSerializer(serializers.ModelSerializer):
    """Serializer for Cart model"""
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = Cart
        fields = ('id', 'customer', 'session_id', 'subtotal', 'tax_amount',
                 'shipping_amount', 'discount_amount', 'total_amount',
                 'applied_discount', 'item_count', 'is_expired', 'items',
                 'created_at', 'updated_at', 'expires_at')
        read_only_fields = ('id', 'subtotal', 'tax_amount', 'shipping_amount',
                           'discount_amount', 'total_amount', 'item_count',
                           'created_at', 'updated_at')


class CartItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for adding items to cart"""
    class Meta:
        model = CartItem
        fields = ('product_id', 'product_name', 'product_sku', 'product_variant',
                 'unit_price', 'quantity')
    
    def validate(self, attrs):
        cart = self.context['cart']
        product_id = attrs['product_id']
        product_variant = attrs.get('product_variant', {})
        
        # Check if item already exists in cart
        existing_item = CartItem.objects.filter(
            cart=cart,
            product_id=product_id,
            product_variant=product_variant
        ).first()
        
        if existing_item:
            # Update quantity instead of creating new item
            existing_item.quantity += attrs['quantity']
            existing_item.save()
            raise serializers.ValidationError("Item already in cart, quantity updated")
        
        return attrs


class CartItemUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating cart items"""
    class Meta:
        model = CartItem
        fields = ('quantity',)
    
    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value


class OrderStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating order status"""
    status = serializers.ChoiceField(choices=Order.ORDER_STATUS)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_status(self, value):
        order = self.context['order']
        if value == 'cancelled' and not order.can_cancel:
            raise serializers.ValidationError("Order cannot be cancelled in current status")
        return value


class PaymentStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating payment status"""
    payment_status = serializers.ChoiceField(choices=Order.PAYMENT_STATUS)
    payment_transaction_id = serializers.CharField(required=False, allow_blank=True)
    payment_gateway = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class FulfillmentStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating fulfillment status"""
    fulfillment_status = serializers.ChoiceField(choices=Order.FULFILLMENT_STATUS)
    tracking_number = serializers.CharField(required=False, allow_blank=True)
    shipping_carrier = serializers.CharField(required=False, allow_blank=True)
    estimated_delivery = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class OrderSearchSerializer(serializers.Serializer):
    """Serializer for order search parameters"""
    order_number = serializers.CharField(required=False)
    customer_email = serializers.EmailField(required=False)
    status = serializers.ChoiceField(choices=Order.ORDER_STATUS, required=False)
    payment_status = serializers.ChoiceField(choices=Order.PAYMENT_STATUS, required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    min_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)


class OrderStatsSerializer(serializers.Serializer):
    """Serializer for order statistics"""
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_order_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    orders_today = serializers.IntegerField()
    orders_this_week = serializers.IntegerField()
    orders_this_month = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    processing_orders = serializers.IntegerField()
    shipped_orders = serializers.IntegerField()
    cancelled_orders = serializers.IntegerField()


class DiscountValidationSerializer(serializers.Serializer):
    """Serializer for validating discount codes"""
    code = serializers.CharField()
    order_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    customer_id = serializers.UUIDField(required=False)
    
    def validate_code(self, value):
        try:
            discount = Discount.objects.get(code=value)
            if not discount.is_valid:
                raise serializers.ValidationError("Discount code is not valid")
        except Discount.DoesNotExist:
            raise serializers.ValidationError("Invalid discount code")
        return value
    
    def validate(self, attrs):
        code = attrs['code']
        order_amount = attrs['order_amount']
        
        try:
            discount = Discount.objects.get(code=code)
            
            # Check minimum order amount
            if order_amount < discount.min_order_amount:
                raise serializers.ValidationError(
                    f"Minimum order amount of {discount.min_order_amount} required"
                )
            
            # Check usage limits
            if discount.max_uses and discount.used_count >= discount.max_uses:
                raise serializers.ValidationError("Discount code usage limit exceeded")
            
            attrs['discount'] = discount
            
        except Discount.DoesNotExist:
            raise serializers.ValidationError("Invalid discount code")
        
        return attrs
