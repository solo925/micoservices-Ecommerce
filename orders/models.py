import uuid
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal


class Customer(models.Model):
    """Customer model for order management"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(unique=True, null=True, blank=True)  # Link to auth service
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    # Addresses
    default_shipping_address = models.JSONField(default=dict, blank=True)
    default_billing_address = models.JSONField(default=dict, blank=True)
    
    # Preferences
    marketing_consent = models.BooleanField(default=False)
    newsletter_subscribed = models.BooleanField(default=False)
    
    # Stats
    total_orders = models.IntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    last_order_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customers'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['user_id']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class Order(models.Model):
    """Enhanced Order model with comprehensive order management"""
    ORDER_STATUS = (
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
    )
    
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('authorized', 'Authorized'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    )
    
    FULFILLMENT_STATUS = (
        ('unfulfilled', 'Unfulfilled'),
        ('fulfilled', 'Fulfilled'),
        ('partially_fulfilled', 'Partially Fulfilled'),
        ('returned', 'Returned'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Customer information
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    customer_email = models.EmailField()
    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=20, blank=True)
    
    # Addresses
    shipping_address = models.JSONField(default=dict)
    billing_address = models.JSONField(default=dict)
    
    # Order details
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Status tracking
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='draft')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    fulfillment_status = models.CharField(max_length=20, choices=FULFILLMENT_STATUS, default='unfulfilled')
    
    # Payment information
    payment_method = models.CharField(max_length=50, blank=True)
    payment_transaction_id = models.CharField(max_length=100, blank=True)
    payment_gateway = models.CharField(max_length=50, blank=True)
    
    # Shipping information
    shipping_method = models.CharField(max_length=50, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    shipping_carrier = models.CharField(max_length=50, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Notes and metadata
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'orders'
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['customer']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Order {self.order_number} - {self.customer_name}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    def generate_order_number(self):
        """Generate unique order number"""
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"ORD-{timestamp}-{random_suffix}"
    
    @property
    def is_paid(self):
        return self.payment_status in ['paid', 'authorized']
    
    @property
    def is_fulfilled(self):
        return self.fulfillment_status in ['fulfilled', 'partially_fulfilled']
    
    @property
    def can_cancel(self):
        return self.status in ['pending', 'confirmed', 'processing']
    
    @property
    def can_refund(self):
        return self.payment_status == 'paid' and self.status in ['shipped', 'delivered']


class OrderItem(models.Model):
    """Order item with detailed product information"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    
    # Product information
    product_id = models.UUIDField(db_index=True)  # Reference to Product service
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=100)
    product_variant = models.JSONField(default=dict, blank=True)  # Size, color, etc.
    
    # Pricing
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Inventory tracking
    inventory_item_id = models.UUIDField(null=True, blank=True)  # Reference to Inventory service
    reserved_quantity = models.PositiveIntegerField(default=0)
    
    # Status
    is_fulfilled = models.BooleanField(default=False)
    fulfilled_quantity = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'order_items'
        indexes = [
            models.Index(fields=['product_id']),
            models.Index(fields=['inventory_item_id']),
        ]
    
    def __str__(self):
        return f"{self.product_name} x {self.quantity} - {self.order.order_number}"
    
    def save(self, *args, **kwargs):
        if not self.total_price:
            self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class OrderHistory(models.Model):
    """Track order status changes and events"""
    EVENT_TYPES = (
        ('created', 'Order Created'),
        ('status_changed', 'Status Changed'),
        ('payment_received', 'Payment Received'),
        ('shipped', 'Order Shipped'),
        ('delivered', 'Order Delivered'),
        ('cancelled', 'Order Cancelled'),
        ('refunded', 'Order Refunded'),
        ('note_added', 'Note Added'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='history')
    
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    description = models.TextField()
    old_value = models.CharField(max_length=100, blank=True)
    new_value = models.CharField(max_length=100, blank=True)
    
    # User who made the change
    user_id = models.UUIDField(null=True, blank=True)
    user_name = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_history'
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['event_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.order.order_number}"


class ShippingMethod(models.Model):
    """Available shipping methods"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    # Pricing
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Delivery time
    estimated_days_min = models.PositiveIntegerField(default=1)
    estimated_days_max = models.PositiveIntegerField(default=7)
    
    # Restrictions
    is_active = models.BooleanField(default=True)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    max_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Geographic restrictions
    available_countries = models.JSONField(default=list, blank=True)
    excluded_countries = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shipping_methods'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class Discount(models.Model):
    """Discount codes and promotions"""
    DISCOUNT_TYPES = (
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
        ('free_shipping', 'Free Shipping'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Discount details
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Usage restrictions
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    
    # Validity
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    
    # Restrictions
    applicable_products = models.JSONField(default=list, blank=True)
    excluded_products = models.JSONField(default=list, blank=True)
    customer_groups = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'discounts'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
            models.Index(fields=['valid_from', 'valid_until']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    @property
    def is_valid(self):
        now = timezone.now()
        return (self.is_active and 
                self.valid_from <= now <= self.valid_until and
                (self.max_uses is None or self.used_count < self.max_uses))


class Cart(models.Model):
    """Shopping cart for customers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='carts', null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    
    # Cart details
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Applied discount
    applied_discount = models.ForeignKey(Discount, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'carts'
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['session_id']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Cart {self.id} - {self.customer.full_name if self.customer else 'Guest'}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def item_count(self):
        return self.items.count()


class CartItem(models.Model):
    """Items in shopping cart"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    
    # Product information
    product_id = models.UUIDField()
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=100)
    product_variant = models.JSONField(default=dict, blank=True)
    
    # Pricing
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_items'
        unique_together = ('cart', 'product_id', 'product_variant')
        indexes = [
            models.Index(fields=['product_id']),
        ]
    
    def __str__(self):
        return f"{self.product_name} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        if not self.total_price:
            self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)
