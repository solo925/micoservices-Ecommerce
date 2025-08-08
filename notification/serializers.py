from rest_framework import serializers
from .models import (
    NotificationTemplate, NotificationChannel, Notification, NotificationDelivery,
    NotificationPreference, NotificationLog, NotificationBatch
)


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class NotificationTemplateCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ['name', 'template_type', 'subject', 'content', 'html_content', 'variables', 'is_active']


class NotificationChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationChannel
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')
        extra_kwargs = {
            'smtp_password': {'write_only': True},
            'sms_api_secret': {'write_only': True},
        }


class NotificationChannelCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationChannel
        fields = [
            'name', 'channel_type', 'is_active', 'smtp_host', 'smtp_port', 'smtp_username',
            'smtp_password', 'smtp_use_tls', 'sms_provider', 'sms_api_key', 'sms_api_secret',
            'sms_from_number', 'webhook_url', 'webhook_headers', 'webhook_method',
            'rate_limit_per_hour', 'rate_limit_per_day'
        ]
        extra_kwargs = {
            'smtp_password': {'write_only': True},
            'sms_api_secret': {'write_only': True},
        }


class NotificationDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDelivery
        fields = '__all__'
        read_only_fields = ('id', 'created_at')


class NotificationSerializer(serializers.ModelSerializer):
    deliveries = NotificationDeliverySerializer(many=True, read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    channel_name = serializers.CharField(source='channel.name', read_only=True)
    
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'sent_at')


class NotificationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'notification_type', 'template', 'channel', 'recipient_email', 'recipient_phone',
            'recipient_user_id', 'subject', 'content', 'html_content', 'priority',
            'metadata', 'context_data', 'scheduled_at', 'expires_at'
        ]


class NotificationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'subject', 'content', 'html_content', 'priority', 'metadata', 'context_data',
            'scheduled_at', 'expires_at', 'max_retries'
        ]


class NotificationStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['delivery_status', 'error_message']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class NotificationPreferenceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'email_enabled', 'email_order_updates', 'email_payment_updates', 'email_promotions',
            'email_newsletter', 'sms_enabled', 'sms_order_updates', 'sms_payment_updates',
            'sms_promotions', 'push_enabled', 'push_order_updates', 'push_payment_updates',
            'push_promotions', 'digest_frequency'
        ]


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = '__all__'
        read_only_fields = ('id', 'created_at')


class NotificationBatchSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    channel_name = serializers.CharField(source='channel.name', read_only=True)
    progress_percentage = serializers.FloatField(read_only=True)
    
    class Meta:
        model = NotificationBatch
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'started_at', 'completed_at')


class NotificationBatchCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationBatch
        fields = [
            'name', 'template', 'channel', 'scheduled_at', 'batch_size', 'delay_between_batches'
        ]


class NotificationBatchStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationBatch
        fields = ['status']


# Specialized serializers for different notification types
class OrderNotificationSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    customer_email = serializers.EmailField()
    customer_name = serializers.CharField(max_length=255)
    order_number = serializers.CharField(max_length=50)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.CharField(max_length=20)
    tracking_number = serializers.CharField(max_length=100, required=False)
    estimated_delivery = serializers.DateField(required=False)


class PaymentNotificationSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    order_id = serializers.UUIDField()
    customer_email = serializers.EmailField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    status = serializers.CharField(max_length=20)
    transaction_id = serializers.CharField(max_length=255)


class LowStockAlertSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    product_name = serializers.CharField(max_length=255)
    current_stock = serializers.IntegerField()
    threshold = serializers.IntegerField()
    warehouse_id = serializers.UUIDField(required=False)


class PromotionNotificationSerializer(serializers.Serializer):
    promotion_id = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    discount_percentage = serializers.IntegerField(required=False)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    valid_until = serializers.DateTimeField()
    code = serializers.CharField(max_length=50, required=False)


class BulkNotificationSerializer(serializers.Serializer):
    template_id = serializers.UUIDField()
    channel_id = serializers.UUIDField()
    recipients = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of recipient dictionaries with email, phone, user_id, and context_data"
    )
    scheduled_at = serializers.DateTimeField(required=False)
    batch_size = serializers.IntegerField(default=100)
    delay_between_batches = serializers.IntegerField(default=60)


class NotificationStatsSerializer(serializers.Serializer):
    total_notifications = serializers.IntegerField()
    sent_notifications = serializers.IntegerField()
    failed_notifications = serializers.IntegerField()
    pending_notifications = serializers.IntegerField()
    delivery_rate = serializers.FloatField()
    average_delivery_time = serializers.FloatField()
    
    # By type
    notifications_by_type = serializers.DictField()
    
    # By channel
    notifications_by_channel = serializers.DictField()
    
    # By status
    notifications_by_status = serializers.DictField()
    
    # Time series data
    notifications_today = serializers.IntegerField()
    notifications_this_week = serializers.IntegerField()
    notifications_this_month = serializers.IntegerField()


class NotificationSearchSerializer(serializers.Serializer):
    notification_type = serializers.CharField(required=False)
    recipient_email = serializers.EmailField(required=False)
    recipient_user_id = serializers.UUIDField(required=False)
    status = serializers.CharField(required=False)
    channel = serializers.UUIDField(required=False)
    template = serializers.UUIDField(required=False)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    priority = serializers.CharField(required=False)


class NotificationRetrySerializer(serializers.Serializer):
    notification_id = serializers.UUIDField()
    force_retry = serializers.BooleanField(default=False)


class NotificationTemplateTestSerializer(serializers.Serializer):
    template_id = serializers.UUIDField()
    test_data = serializers.DictField(
        help_text="Test data to populate template variables"
    )
    channel_id = serializers.UUIDField(required=False)
    recipient_email = serializers.EmailField(required=False)
    recipient_phone = serializers.CharField(max_length=20, required=False)


class NotificationChannelTestSerializer(serializers.Serializer):
    channel_id = serializers.UUIDField()
    test_email = serializers.EmailField(required=False)
    test_phone = serializers.CharField(max_length=20, required=False)
    test_message = serializers.CharField(max_length=500, default="Test notification")


class NotificationPreferenceBulkUpdateSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        help_text="List of user IDs to update preferences for"
    )
    preferences = NotificationPreferenceUpdateSerializer()
