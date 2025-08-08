from rest_framework import serializers
from .models import Event, EventSubscription, EventDelivery


class EventSerializer(serializers.ModelSerializer):
    """Serializer for Event model"""
    
    class Meta:
        model = Event
        fields = [
            'id', 'event_type', 'source_service', 'target_service',
            'correlation_id', 'causation_id', 'data', 'metadata',
            'status', 'priority', 'retry_count', 'max_retries',
            'created_at', 'processed_at', 'scheduled_at', 'expires_at',
            'error_message', 'error_details'
        ]
        read_only_fields = [
            'id', 'created_at', 'processed_at', 'retry_count',
            'error_message', 'error_details'
        ]


class EventCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating events"""
    
    class Meta:
        model = Event
        fields = [
            'event_type', 'source_service', 'target_service',
            'correlation_id', 'causation_id', 'data', 'metadata',
            'priority', 'max_retries', 'scheduled_at', 'expires_at'
        ]
    
    def validate_event_type(self, value):
        """Validate event type"""
        valid_types = [choice[0] for choice in Event.EVENT_TYPES]
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid event type. Must be one of: {valid_types}")
        return value
    
    def validate_priority(self, value):
        """Validate priority"""
        if value < 0 or value > 10:
            raise serializers.ValidationError("Priority must be between 0 and 10")
        return value


class EventSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for EventSubscription model"""
    
    class Meta:
        model = EventSubscription
        fields = [
            'id', 'subscriber_service', 'event_type', 'source_service',
            'endpoint_url', 'is_active', 'retry_count', 'timeout_seconds',
            'auth_type', 'auth_credentials', 'rate_limit_per_minute',
            'rate_limit_per_hour', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EventSubscriptionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating event subscriptions"""
    
    class Meta:
        model = EventSubscription
        fields = [
            'subscriber_service', 'event_type', 'source_service',
            'endpoint_url', 'is_active', 'retry_count', 'timeout_seconds',
            'auth_type', 'auth_credentials', 'rate_limit_per_minute',
            'rate_limit_per_hour'
        ]
    
    def validate_event_type(self, value):
        """Validate event type"""
        valid_types = [choice[0] for choice in Event.EVENT_TYPES]
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid event type. Must be one of: {valid_types}")
        return value
    
    def validate_auth_type(self, value):
        """Validate auth type"""
        valid_types = ['none', 'basic', 'bearer', 'api_key']
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid auth type. Must be one of: {valid_types}")
        return value
    
    def validate_endpoint_url(self, value):
        """Validate endpoint URL"""
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Endpoint URL must start with http:// or https://")
        return value


class EventDeliverySerializer(serializers.ModelSerializer):
    """Serializer for EventDelivery model"""
    
    event = EventSerializer(read_only=True)
    subscription = EventSubscriptionSerializer(read_only=True)
    
    class Meta:
        model = EventDelivery
        fields = [
            'id', 'event', 'subscription', 'status', 'attempt_count',
            'max_attempts', 'sent_at', 'delivered_at', 'response_status',
            'response_body', 'error_message', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'event', 'subscription', 'sent_at', 'delivered_at',
            'response_status', 'response_body', 'error_message',
            'created_at', 'updated_at'
        ]


class EventStatsSerializer(serializers.Serializer):
    """Serializer for event statistics"""
    
    total_events = serializers.IntegerField()
    events_by_type = serializers.DictField(child=serializers.IntegerField())
    events_by_status = serializers.DictField(child=serializers.IntegerField())
    events_by_service = serializers.DictField(child=serializers.IntegerField())
    delivery_stats = serializers.DictField()


class EventSearchSerializer(serializers.Serializer):
    """Serializer for event search parameters"""
    
    event_type = serializers.CharField(required=False)
    source_service = serializers.CharField(required=False)
    target_service = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    correlation_id = serializers.UUIDField(required=False)
    priority_min = serializers.IntegerField(required=False, min_value=0, max_value=10)
    priority_max = serializers.IntegerField(required=False, min_value=0, max_value=10)
    
    def validate(self, data):
        """Validate search parameters"""
        if 'start_date' in data and 'end_date' in data:
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError("Start date must be before end date")
        
        if 'priority_min' in data and 'priority_max' in data:
            if data['priority_min'] > data['priority_max']:
                raise serializers.ValidationError("Priority min must be less than priority max")
        
        return data


class EventRetrySerializer(serializers.Serializer):
    """Serializer for event retry operations"""
    
    event_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    max_retries = serializers.IntegerField(min_value=1, max_value=10, default=3)
    force_retry = serializers.BooleanField(default=False)


class EventBulkCreateSerializer(serializers.Serializer):
    """Serializer for bulk event creation"""
    
    events = serializers.ListField(
        child=EventCreateSerializer(),
        min_length=1,
        max_length=100
    )
    
    def validate_events(self, value):
        """Validate events list"""
        if len(value) > 100:
            raise serializers.ValidationError("Cannot create more than 100 events at once")
        return value


class EventSubscriptionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating event subscriptions"""
    
    class Meta:
        model = EventSubscription
        fields = [
            'endpoint_url', 'is_active', 'retry_count', 'timeout_seconds',
            'auth_type', 'auth_credentials', 'rate_limit_per_minute',
            'rate_limit_per_hour'
        ]


class EventDeliveryRetrySerializer(serializers.Serializer):
    """Serializer for delivery retry operations"""
    
    delivery_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    max_attempts = serializers.IntegerField(min_value=1, max_value=10, default=3)


class EventWebhookSerializer(serializers.Serializer):
    """Serializer for webhook event data"""
    
    event_type = serializers.CharField()
    source_service = serializers.CharField()
    data = serializers.DictField(default=dict)
    metadata = serializers.DictField(default=dict)
    target_service = serializers.CharField(required=False, allow_blank=True)
    correlation_id = serializers.UUIDField(required=False)
    causation_id = serializers.UUIDField(required=False)
    priority = serializers.IntegerField(min_value=0, max_value=10, default=0)
    scheduled_at = serializers.DateTimeField(required=False)
    expires_at = serializers.DateTimeField(required=False)
    
    def validate_event_type(self, value):
        """Validate event type"""
        valid_types = [choice[0] for choice in Event.EVENT_TYPES]
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid event type. Must be one of: {valid_types}")
        return value
