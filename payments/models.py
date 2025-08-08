import uuid
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal


class PaymentProvider(models.Model):
    """Payment service providers (Stripe, PayPal, etc.)"""
    PROVIDER_TYPES = (
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('square', 'Square'),
        ('adyen', 'Adyen'),
        ('braintree', 'Braintree'),
        ('razorpay', 'Razorpay'),
        ('custom', 'Custom'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=20, choices=PROVIDER_TYPES)
    is_active = models.BooleanField(default=True)
    
    # Configuration
    api_key = models.CharField(max_length=255, blank=True)
    secret_key = models.CharField(max_length=255, blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True)
    config = models.JSONField(default=dict, blank=True)  # Additional provider-specific config
    
    # Features
    supports_credit_cards = models.BooleanField(default=True)
    supports_debit_cards = models.BooleanField(default=True)
    supports_bank_transfers = models.BooleanField(default=False)
    supports_digital_wallets = models.BooleanField(default=False)
    supports_cryptocurrency = models.BooleanField(default=False)
    
    # Processing fees
    processing_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    processing_fee_fixed = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payment_providers'
        indexes = [
            models.Index(fields=['provider_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.provider_type})"


class PaymentMethod(models.Model):
    """Customer payment methods (cards, bank accounts, etc.)"""
    METHOD_TYPES = (
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('digital_wallet', 'Digital Wallet'),
        ('cryptocurrency', 'Cryptocurrency'),
        ('cash_on_delivery', 'Cash on Delivery'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer_id = models.UUIDField(db_index=True)  # Link to customer
    
    # Payment method details
    method_type = models.CharField(max_length=20, choices=METHOD_TYPES)
    provider = models.ForeignKey(PaymentProvider, on_delete=models.CASCADE, null=True, blank=True)
    
    # Card information (encrypted in production)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=20, blank=True)  # visa, mastercard, etc.
    card_exp_month = models.PositiveIntegerField(null=True, blank=True)
    card_exp_year = models.PositiveIntegerField(null=True, blank=True)
    
    # Provider-specific data
    provider_payment_method_id = models.CharField(max_length=255, blank=True)
    provider_customer_id = models.CharField(max_length=255, blank=True)
    
    # Status
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Metadata
    billing_address = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payment_methods'
        indexes = [
            models.Index(fields=['customer_id']),
            models.Index(fields=['method_type']),
            models.Index(fields=['is_default']),
        ]
    
    def __str__(self):
        if self.card_last4:
            return f"{self.card_brand.title()} ****{self.card_last4}"
        return f"{self.get_method_type_display()}"


class Payment(models.Model):
    """Enhanced Payment model with comprehensive payment processing"""
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('authorized', 'Authorized'),
        ('captured', 'Captured'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
        ('disputed', 'Disputed'),
    )
    
    PAYMENT_INTENT_STATUS = (
        ('requires_payment_method', 'Requires Payment Method'),
        ('requires_confirmation', 'Requires Confirmation'),
        ('requires_action', 'Requires Action'),
        ('processing', 'Processing'),
        ('requires_capture', 'Requires Capture'),
        ('canceled', 'Canceled'),
        ('succeeded', 'Succeeded'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.UUIDField(db_index=True)  # Reference to Order service
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True)
    provider = models.ForeignKey(PaymentProvider, on_delete=models.CASCADE)
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    currency = models.CharField(max_length=3, default='USD')
    description = models.TextField(blank=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    intent_status = models.CharField(max_length=30, choices=PAYMENT_INTENT_STATUS, blank=True)
    
    # Provider-specific data
    provider_payment_id = models.CharField(max_length=255, blank=True)
    provider_intent_id = models.CharField(max_length=255, blank=True)
    provider_charge_id = models.CharField(max_length=255, blank=True)
    
    # Transaction details
    transaction_id = models.CharField(max_length=255, unique=True, db_index=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    
    # Fees and amounts
    processing_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    authorized_at = models.DateTimeField(null=True, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'payments'
        indexes = [
            models.Index(fields=['order_id']),
            models.Index(fields=['status']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Payment {self.transaction_id} - {self.amount} {self.currency}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()
        super().save(*args, **kwargs)
    
    def generate_transaction_id(self):
        """Generate unique transaction ID"""
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"TXN-{timestamp}-{random_suffix}"
    
    @property
    def is_successful(self):
        return self.status in ['succeeded', 'captured']
    
    @property
    def is_failed(self):
        return self.status in ['failed', 'cancelled']
    
    @property
    def is_refunded(self):
        return self.status in ['refunded', 'partially_refunded']
    
    @property
    def can_refund(self):
        return self.is_successful and not self.is_refunded
    
    @property
    def refundable_amount(self):
        return self.amount - self.refunded_amount


class Refund(models.Model):
    """Payment refunds"""
    REFUND_STATUS = (
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    
    REFUND_REASONS = (
        ('duplicate', 'Duplicate'),
        ('fraudulent', 'Fraudulent'),
        ('requested_by_customer', 'Requested by Customer'),
        ('defective_product', 'Defective Product'),
        ('not_received', 'Not Received'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds')
    
    # Refund details
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    currency = models.CharField(max_length=3, default='USD')
    reason = models.CharField(max_length=30, choices=REFUND_REASONS)
    description = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=REFUND_STATUS, default='pending')
    
    # Provider data
    provider_refund_id = models.CharField(max_length=255, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'refunds'
        indexes = [
            models.Index(fields=['payment']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Refund {self.id} - {self.amount} {self.currency}"


class Subscription(models.Model):
    """Recurring payment subscriptions"""
    SUBSCRIPTION_STATUS = (
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('unpaid', 'Unpaid'),
        ('trialing', 'Trialing'),
        ('paused', 'Paused'),
    )
    
    INTERVAL_TYPES = (
        ('day', 'Daily'),
        ('week', 'Weekly'),
        ('month', 'Monthly'),
        ('year', 'Yearly'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer_id = models.UUIDField(db_index=True)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True)
    provider = models.ForeignKey(PaymentProvider, on_delete=models.CASCADE)
    
    # Subscription details
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Billing cycle
    interval = models.CharField(max_length=10, choices=INTERVAL_TYPES, default='month')
    interval_count = models.PositiveIntegerField(default=1)
    
    # Status and dates
    status = models.CharField(max_length=20, choices=SUBSCRIPTION_STATUS, default='active')
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    
    # Provider data
    provider_subscription_id = models.CharField(max_length=255, blank=True)
    provider_customer_id = models.CharField(max_length=255, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions'
        indexes = [
            models.Index(fields=['customer_id']),
            models.Index(fields=['status']),
            models.Index(fields=['current_period_end']),
        ]
    
    def __str__(self):
        return f"Subscription {self.name} - {self.customer_id}"


class Invoice(models.Model):
    """Subscription invoices"""
    INVOICE_STATUS = (
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('paid', 'Paid'),
        ('uncollectible', 'Uncollectible'),
        ('void', 'Void'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='invoices')
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Invoice details
    number = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    description = models.TextField(blank=True)
    
    # Status and dates
    status = models.CharField(max_length=20, choices=INVOICE_STATUS, default='draft')
    due_date = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Provider data
    provider_invoice_id = models.CharField(max_length=255, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'invoices'
        indexes = [
            models.Index(fields=['subscription']),
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        return f"Invoice {self.number} - {self.amount} {self.currency}"


class PaymentWebhook(models.Model):
    """Webhook events from payment providers"""
    WEBHOOK_STATUS = (
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(PaymentProvider, on_delete=models.CASCADE)
    
    # Webhook details
    event_type = models.CharField(max_length=100)
    provider_event_id = models.CharField(max_length=255, blank=True)
    
    # Payload and processing
    raw_payload = models.JSONField()
    processed_payload = models.JSONField(default=dict, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=WEBHOOK_STATUS, default='pending')
    error_message = models.TextField(blank=True)
    
    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'payment_webhooks'
        indexes = [
            models.Index(fields=['provider']),
            models.Index(fields=['event_type']),
            models.Index(fields=['status']),
            models.Index(fields=['received_at']),
        ]
    
    def __str__(self):
        return f"Webhook {self.event_type} - {self.provider.name}"


class PaymentDispute(models.Model):
    """Payment disputes and chargebacks"""
    DISPUTE_STATUS = (
        ('warning_needs_response', 'Warning Needs Response'),
        ('warning_under_review', 'Warning Under Review'),
        ('warning_closed', 'Warning Closed'),
        ('needs_response', 'Needs Response'),
        ('under_review', 'Under Review'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    )
    
    DISPUTE_REASONS = (
        ('duplicate', 'Duplicate'),
        ('fraudulent', 'Fraudulent'),
        ('subscription_canceled', 'Subscription Canceled'),
        ('product_not_received', 'Product Not Received'),
        ('product_unacceptable', 'Product Unacceptable'),
        ('credit_not_processed', 'Credit Not Processed'),
        ('general', 'General'),
        ('incorrect_account_details', 'Incorrect Account Details'),
        ('insufficient_funds', 'Insufficient Funds'),
        ('product_not_as_described', 'Product Not As Described'),
        ('customer_initiated', 'Customer Initiated'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='disputes')
    
    # Dispute details
    provider_dispute_id = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    reason = models.CharField(max_length=30, choices=DISPUTE_REASONS)
    description = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=30, choices=DISPUTE_STATUS, default='needs_response')
    
    # Evidence and response
    evidence = models.JSONField(default=dict, blank=True)
    response_deadline = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'payment_disputes'
        indexes = [
            models.Index(fields=['payment']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Dispute {self.id} - {self.amount} {self.currency}"
