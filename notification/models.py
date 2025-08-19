import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal


class NotificationTemplate(models.Model):
    """Template for notifications with support for multiple channels"""
    TEMPLATE_TYPE = (
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('webhook', 'Webhook'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE)
    subject = models.CharField(max_length=255, blank=True) 
    content = models.TextField() 
    html_content = models.TextField(blank=True) 
    variables = models.JSONField(default=dict, blank=True) 
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class NotificationChannel(models.Model):
    """Configuration for different notification channels"""
    CHANNEL_TYPE = (
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('webhook', 'Webhook'),
        ('slack', 'Slack'),
        ('discord', 'Discord'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPE)
    is_active = models.BooleanField(default=True)
    
    # Email configuration
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.IntegerField(default=587, blank=True)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    
    # SMS configuration
    sms_provider = models.CharField(max_length=50, blank=True)
    sms_api_key = models.CharField(max_length=255, blank=True)
    sms_api_secret = models.CharField(max_length=255, blank=True)
    sms_from_number = models.CharField(max_length=20, blank=True)
    
    # Webhook configuration
    webhook_url = models.URLField(blank=True)
    webhook_headers = models.JSONField(default=dict, blank=True)
    webhook_method = models.CharField(max_length=10, default='POST', blank=True)
    
    # Rate limiting
    rate_limit_per_hour = models.IntegerField(default=100)
    rate_limit_per_day = models.IntegerField(default=1000)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()})"


class Notification(models.Model):
    """Main notification model"""
    NOTIFICATION_TYPE = (
        ('order_confirmation', 'Order Confirmation'),
        ('order_shipped', 'Order Shipped'),
        ('order_delivered', 'Order Delivered'),
        ('payment_success', 'Payment Success'),
        ('payment_failed', 'Payment Failed'),
        ('refund_processed', 'Refund Processed'),
        ('low_stock_alert', 'Low Stock Alert'),
        ('price_change', 'Price Change'),
        ('promotion', 'Promotion'),
        ('account_verification', 'Account Verification'),
        ('password_reset', 'Password Reset'),
        ('welcome', 'Welcome'),
        ('custom', 'Custom'),
    )
    
    PRIORITY_LEVEL = (
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    channel = models.ForeignKey(NotificationChannel, on_delete=models.CASCADE)
    
    # Recipient information
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    recipient_user_id = models.UUIDField(null=True, blank=True)
    
    # Content
    subject = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    html_content = models.TextField(blank=True)
    
    # Metadata
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVEL, default='normal')
    metadata = models.JSONField(default=dict, blank=True)
    context_data = models.JSONField(default=dict, blank=True) 
    
    # Status tracking
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivery_status = models.CharField(max_length=20, default='pending')
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    
    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['notification_type']),
            models.Index(fields=['recipient_email']),
            models.Index(fields=['recipient_user_id']),
            models.Index(fields=['is_sent', 'scheduled_at']),
        ]
    
    def __str__(self):
        return f"{self.notification_type} to {self.recipient_email or self.recipient_phone}"
    
    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def can_retry(self):
        return self.retry_count < self.max_retries and not self.is_sent


class NotificationDelivery(models.Model):
    """Track delivery attempts and results"""
    DELIVERY_STATUS = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
        ('spam', 'Marked as Spam'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='deliveries')
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=DELIVERY_STATUS, default='pending')
    
    # Provider response
    provider_message_id = models.CharField(max_length=255, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    
    # Timing
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['notification', 'attempt_number']
    
    def __str__(self):
        return f"Delivery {self.attempt_number} for {self.notification}"


class NotificationPreference(models.Model):
    """User notification preferences"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(unique=True)
    
    # Email preferences
    email_enabled = models.BooleanField(default=True)
    email_order_updates = models.BooleanField(default=True)
    email_payment_updates = models.BooleanField(default=True)
    email_promotions = models.BooleanField(default=True)
    email_newsletter = models.BooleanField(default=False)
    
    # SMS preferences
    sms_enabled = models.BooleanField(default=False)
    sms_order_updates = models.BooleanField(default=False)
    sms_payment_updates = models.BooleanField(default=False)
    sms_promotions = models.BooleanField(default=False)
    
    # Push notification preferences
    push_enabled = models.BooleanField(default=True)
    push_order_updates = models.BooleanField(default=True)
    push_payment_updates = models.BooleanField(default=True)
    push_promotions = models.BooleanField(default=False)
    
    # Frequency preferences
    digest_frequency = models.CharField(max_length=20, default='immediate', choices=[
        ('immediate', 'Immediate'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Preferences for user {self.user_id}"


class NotificationLog(models.Model):
    """Audit log for notification activities"""
    LOG_LEVEL = (
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('debug', 'Debug'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    level = models.CharField(max_length=10, choices=LOG_LEVEL, default='info')
    message = models.TextField()
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, null=True, blank=True)
    channel = models.ForeignKey(NotificationChannel, on_delete=models.CASCADE, null=True, blank=True)
    
    # Additional context
    context_data = models.JSONField(default=dict, blank=True)
    user_id = models.UUIDField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.level}: {self.message[:50]}"


class NotificationBatch(models.Model):
    """For bulk notifications"""
    BATCH_STATUS = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.CASCADE)
    channel = models.ForeignKey(NotificationChannel, on_delete=models.CASCADE)
    
    # Batch configuration
    status = models.CharField(max_length=20, choices=BATCH_STATUS, default='pending')
    total_recipients = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    
    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Configuration
    batch_size = models.PositiveIntegerField(default=100)
    delay_between_batches = models.PositiveIntegerField(default=60)  # seconds
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.status})"
    
    @property
    def progress_percentage(self):
        if self.total_recipients == 0:
            return 0
        return (self.sent_count + self.failed_count) / self.total_recipients * 100
