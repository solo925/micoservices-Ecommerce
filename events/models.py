import uuid
import json
from django.db import models
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder


class Event(models.Model):
    """Event model for event-driven communication between microservices"""
    
    EVENT_TYPES = (
        # Product events
        ('product.created', 'Product Created'),
        ('product.updated', 'Product Updated'),
        ('product.deleted', 'Product Deleted'),
        ('product.stock_changed', 'Product Stock Changed'),
        
        # Order events
        ('order.created', 'Order Created'),
        ('order.status_changed', 'Order Status Changed'),
        ('order.cancelled', 'Order Cancelled'),
        ('order.shipped', 'Order Shipped'),
        ('order.delivered', 'Order Delivered'),
        
        # Payment events
        ('payment.created', 'Payment Created'),
        ('payment.succeeded', 'Payment Succeeded'),
        ('payment.failed', 'Payment Failed'),
        ('payment.refunded', 'Payment Refunded'),
        
        # Customer events
        ('customer.registered', 'Customer Registered'),
        ('customer.updated', 'Customer Updated'),
        ('customer.deleted', 'Customer Deleted'),
        
        # Inventory events
        ('inventory.low_stock', 'Low Stock Alert'),
        ('inventory.out_of_stock', 'Out of Stock'),
        ('inventory.stock_reserved', 'Stock Reserved'),
        ('inventory.stock_released', 'Stock Released'),
        
        # Notification events
        ('notification.sent', 'Notification Sent'),
        ('notification.failed', 'Notification Failed'),
        ('notification.delivered', 'Notification Delivered'),
        
        # System events
        ('system.health_check', 'System Health Check'),
        ('system.error', 'System Error'),
        ('system.maintenance', 'System Maintenance'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('retry', 'Retry'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    source_service = models.CharField(max_length=50)  # e.g., 'products', 'orders', 'payments'
    target_service = models.CharField(max_length=50, blank=True)  # Optional target service
    correlation_id = models.UUIDField(null=True, blank=True)  # For tracking related events
    causation_id = models.UUIDField(null=True, blank=True)  # ID of the event that caused this event
    
    # Event data
    data = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    metadata = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    
    # Status and timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.IntegerField(default=0)  # Higher number = higher priority
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)  # For delayed events
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'events'
        indexes = [
            models.Index(fields=['event_type']),
            models.Index(fields=['source_service']),
            models.Index(fields=['target_service']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['correlation_id']),
            models.Index(fields=['scheduled_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.event_type} from {self.source_service} ({self.status})"
    
    @property
    def is_expired(self):
        """Check if the event has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def can_retry(self):
        """Check if the event can be retried"""
        return self.retry_count < self.max_retries and self.status in ['failed', 'retry']
    
    def mark_processing(self):
        """Mark event as processing"""
        self.status = 'processing'
        self.save(update_fields=['status'])
    
    def mark_completed(self):
        """Mark event as completed"""
        self.status = 'completed'
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_at'])
    
    def mark_failed(self, error_message="", error_details=None):
        """Mark event as failed"""
        self.status = 'failed'
        self.error_message = error_message
        if error_details:
            self.error_details = error_details
        self.save(update_fields=['status', 'error_message', 'error_details'])
    
    def increment_retry(self):
        """Increment retry count"""
        self.retry_count += 1
        if self.retry_count >= self.max_retries:
            self.status = 'failed'
        else:
            self.status = 'retry'
        self.save(update_fields=['retry_count', 'status'])


class EventSubscription(models.Model):
    """Model for managing event subscriptions between services"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscriber_service = models.CharField(max_length=50)  # Service that subscribes to events
    event_type = models.CharField(max_length=50)  # Event type to subscribe to
    source_service = models.CharField(max_length=50, blank=True)  # Optional source service filter
    endpoint_url = models.URLField()  # Webhook endpoint for the subscriber
    is_active = models.BooleanField(default=True)
    retry_count = models.PositiveIntegerField(default=3)
    timeout_seconds = models.PositiveIntegerField(default=30)
    
    # Authentication
    auth_type = models.CharField(max_length=20, choices=(
        ('none', 'None'),
        ('basic', 'Basic Auth'),
        ('bearer', 'Bearer Token'),
        ('api_key', 'API Key'),
    ), default='none')
    auth_credentials = models.JSONField(default=dict, blank=True)  # Store auth details securely
    
    # Rate limiting
    rate_limit_per_minute = models.PositiveIntegerField(default=60)
    rate_limit_per_hour = models.PositiveIntegerField(default=1000)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'event_subscriptions'
        unique_together = ['subscriber_service', 'event_type', 'source_service']
        indexes = [
            models.Index(fields=['subscriber_service']),
            models.Index(fields=['event_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.subscriber_service} -> {self.event_type}"


class EventDelivery(models.Model):
    """Model for tracking event delivery attempts"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('retry', 'Retry'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='deliveries')
    subscription = models.ForeignKey(EventSubscription, on_delete=models.CASCADE, related_name='deliveries')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    
    # Delivery details
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'event_deliveries'
        indexes = [
            models.Index(fields=['event']),
            models.Index(fields=['subscription']),
            models.Index(fields=['status']),
            models.Index(fields=['sent_at']),
        ]
    
    def __str__(self):
        return f"Delivery {self.id} for {self.event.event_type}"
    
    def mark_sent(self):
        """Mark delivery as sent"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_delivered(self, response_status=None, response_body=""):
        """Mark delivery as delivered"""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        if response_status:
            self.response_status = response_status
        if response_body:
            self.response_body = response_body
        self.save(update_fields=['status', 'delivered_at', 'response_status', 'response_body'])
    
    def mark_failed(self, error_message="", response_status=None):
        """Mark delivery as failed"""
        self.status = 'failed'
        self.error_message = error_message
        if response_status:
            self.response_status = response_status
        self.save(update_fields=['status', 'error_message', 'response_status'])
    
    def increment_attempt(self):
        """Increment attempt count"""
        self.attempt_count += 1
        if self.attempt_count >= self.max_attempts:
            self.status = 'failed'
        else:
            self.status = 'retry'
        self.save(update_fields=['attempt_count', 'status'])
