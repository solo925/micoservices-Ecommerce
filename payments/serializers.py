from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from .models import (
    PaymentProvider, PaymentMethod, Payment, Refund, Subscription,
    Invoice, PaymentWebhook, PaymentDispute
)


class PaymentProviderSerializer(serializers.ModelSerializer):
    """Serializer for PaymentProvider model"""
    class Meta:
        model = PaymentProvider
        fields = ('id', 'name', 'provider_type', 'is_active', 'supports_credit_cards',
                 'supports_debit_cards', 'supports_bank_transfers', 'supports_digital_wallets',
                 'supports_cryptocurrency', 'processing_fee_percentage', 'processing_fee_fixed',
                 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class PaymentProviderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payment providers"""
    class Meta:
        model = PaymentProvider
        fields = ('name', 'provider_type', 'is_active', 'api_key', 'secret_key',
                 'webhook_secret', 'config', 'supports_credit_cards', 'supports_debit_cards',
                 'supports_bank_transfers', 'supports_digital_wallets', 'supports_cryptocurrency',
                 'processing_fee_percentage', 'processing_fee_fixed')


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for PaymentMethod model"""
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    
    class Meta:
        model = PaymentMethod
        fields = ('id', 'customer_id', 'method_type', 'provider', 'provider_name',
                 'card_last4', 'card_brand', 'card_exp_month', 'card_exp_year',
                 'provider_payment_method_id', 'provider_customer_id', 'is_default',
                 'is_active', 'billing_address', 'metadata', 'created_at', 'updated_at')
        read_only_fields = ('id', 'provider_payment_method_id', 'provider_customer_id',
                           'created_at', 'updated_at')


class PaymentMethodCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payment methods"""
    # Card details for tokenization
    card_number = serializers.CharField(write_only=True, required=False)
    card_cvc = serializers.CharField(write_only=True, required=False)
    card_expiry = serializers.CharField(write_only=True, required=False)  # MM/YY format
    
    class Meta:
        model = PaymentMethod
        fields = ('customer_id', 'method_type', 'provider', 'card_number', 'card_cvc',
                 'card_expiry', 'billing_address', 'metadata', 'is_default')
    
    def validate(self, attrs):
        method_type = attrs.get('method_type')
        
        if method_type in ['credit_card', 'debit_card']:
            if not all(key in attrs for key in ['card_number', 'card_cvc', 'card_expiry']):
                raise serializers.ValidationError(
                    "Card details are required for credit/debit card payment methods"
                )
        
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    payment_method_display = serializers.CharField(source='payment_method.__str__', read_only=True)
    is_successful = serializers.ReadOnlyField()
    is_failed = serializers.ReadOnlyField()
    is_refunded = serializers.ReadOnlyField()
    can_refund = serializers.ReadOnlyField()
    refundable_amount = serializers.ReadOnlyField()
    
    class Meta:
        model = Payment
        fields = ('id', 'order_id', 'payment_method', 'payment_method_display', 'provider',
                 'provider_name', 'amount', 'currency', 'description', 'status', 'intent_status',
                 'provider_payment_id', 'provider_intent_id', 'provider_charge_id',
                 'transaction_id', 'gateway_response', 'error_message', 'error_code',
                 'processing_fee', 'tax_amount', 'refunded_amount', 'is_successful',
                 'is_failed', 'is_refunded', 'can_refund', 'refundable_amount',
                 'metadata', 'created_at', 'updated_at', 'authorized_at', 'captured_at',
                 'failed_at', 'refunded_at')
        read_only_fields = ('id', 'transaction_id', 'gateway_response', 'error_message',
                           'error_code', 'processing_fee', 'refunded_amount', 'created_at',
                           'updated_at', 'authorized_at', 'captured_at', 'failed_at', 'refunded_at')


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payments"""
    payment_method_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = Payment
        fields = ('order_id', 'payment_method_id', 'provider', 'amount', 'currency',
                 'description', 'metadata')
    
    def validate(self, attrs):
        amount = attrs.get('amount')
        if amount and amount <= 0:
            raise serializers.ValidationError("Payment amount must be greater than 0")
        
        return attrs


class PaymentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating payments"""
    class Meta:
        model = Payment
        fields = ('status', 'intent_status', 'gateway_response', 'error_message', 'error_code')
    
    def update(self, instance, validated_data):
        # Update timestamps based on status changes
        if 'status' in validated_data:
            new_status = validated_data['status']
            if new_status == 'authorized':
                instance.authorized_at = timezone.now()
            elif new_status == 'captured':
                instance.captured_at = timezone.now()
            elif new_status == 'failed':
                instance.failed_at = timezone.now()
            elif new_status in ['refunded', 'partially_refunded']:
                instance.refunded_at = timezone.now()
        
        return super().update(instance, validated_data)


class RefundSerializer(serializers.ModelSerializer):
    """Serializer for Refund model"""
    payment_transaction_id = serializers.CharField(source='payment.transaction_id', read_only=True)
    
    class Meta:
        model = Refund
        fields = ('id', 'payment', 'payment_transaction_id', 'amount', 'currency', 'reason',
                 'description', 'status', 'provider_refund_id', 'gateway_response',
                 'error_message', 'metadata', 'created_at', 'updated_at', 'processed_at')
        read_only_fields = ('id', 'provider_refund_id', 'gateway_response', 'error_message',
                           'created_at', 'updated_at', 'processed_at')


class RefundCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating refunds"""
    class Meta:
        model = Refund
        fields = ('payment', 'amount', 'currency', 'reason', 'description', 'metadata')
    
    def validate(self, attrs):
        payment = attrs.get('payment')
        amount = attrs.get('amount')
        
        if payment and amount:
            if amount > payment.refundable_amount:
                raise serializers.ValidationError(
                    f"Refund amount cannot exceed refundable amount ({payment.refundable_amount})"
                )
        
        return attrs


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Subscription model"""
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    payment_method_display = serializers.CharField(source='payment_method.__str__', read_only=True)
    
    class Meta:
        model = Subscription
        fields = ('id', 'customer_id', 'payment_method', 'payment_method_display', 'provider',
                 'provider_name', 'name', 'description', 'amount', 'currency', 'interval',
                 'interval_count', 'status', 'current_period_start', 'current_period_end',
                 'trial_start', 'trial_end', 'canceled_at', 'provider_subscription_id',
                 'provider_customer_id', 'metadata', 'created_at', 'updated_at')
        read_only_fields = ('id', 'provider_subscription_id', 'provider_customer_id',
                           'created_at', 'updated_at', 'canceled_at')


class SubscriptionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating subscriptions"""
    class Meta:
        model = Subscription
        fields = ('customer_id', 'payment_method', 'provider', 'name', 'description',
                 'amount', 'currency', 'interval', 'interval_count', 'current_period_start',
                 'current_period_end', 'trial_start', 'trial_end', 'metadata')
    
    def validate(self, attrs):
        current_period_start = attrs.get('current_period_start')
        current_period_end = attrs.get('current_period_end')
        
        if current_period_start and current_period_end:
            if current_period_end <= current_period_start:
                raise serializers.ValidationError(
                    "Current period end must be after current period start"
                )
        
        return attrs


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for Invoice model"""
    subscription_name = serializers.CharField(source='subscription.name', read_only=True)
    payment_transaction_id = serializers.CharField(source='payment.transaction_id', read_only=True)
    
    class Meta:
        model = Invoice
        fields = ('id', 'subscription', 'subscription_name', 'payment', 'payment_transaction_id',
                 'number', 'amount', 'currency', 'description', 'status', 'due_date',
                 'paid_at', 'provider_invoice_id', 'metadata', 'created_at', 'updated_at')
        read_only_fields = ('id', 'number', 'provider_invoice_id', 'created_at', 'updated_at')


class PaymentWebhookSerializer(serializers.ModelSerializer):
    """Serializer for PaymentWebhook model"""
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    
    class Meta:
        model = PaymentWebhook
        fields = ('id', 'provider', 'provider_name', 'event_type', 'provider_event_id',
                 'raw_payload', 'processed_payload', 'status', 'error_message',
                 'received_at', 'processed_at')
        read_only_fields = ('id', 'received_at', 'processed_at')


class PaymentDisputeSerializer(serializers.ModelSerializer):
    """Serializer for PaymentDispute model"""
    payment_transaction_id = serializers.CharField(source='payment.transaction_id', read_only=True)
    
    class Meta:
        model = PaymentDispute
        fields = ('id', 'payment', 'payment_transaction_id', 'provider_dispute_id',
                 'amount', 'currency', 'reason', 'description', 'status', 'evidence',
                 'response_deadline', 'created_at', 'updated_at', 'closed_at')
        read_only_fields = ('id', 'provider_dispute_id', 'created_at', 'updated_at', 'closed_at')


class PaymentIntentSerializer(serializers.Serializer):
    """Serializer for creating payment intents"""
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField(max_length=3, default='USD')
    payment_method_id = serializers.UUIDField(required=False)
    customer_id = serializers.UUIDField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value


class PaymentConfirmSerializer(serializers.Serializer):
    """Serializer for confirming payments"""
    payment_intent_id = serializers.CharField()
    payment_method_id = serializers.UUIDField(required=False)
    return_url = serializers.URLField(required=False)


class RefundRequestSerializer(serializers.Serializer):
    """Serializer for refund requests"""
    payment_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    reason = serializers.ChoiceField(choices=Refund.REFUND_REASONS)
    description = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        payment_id = attrs.get('payment_id')
        amount = attrs.get('amount')
        
        try:
            payment = Payment.objects.get(id=payment_id)
            if not payment.can_refund:
                raise serializers.ValidationError("Payment cannot be refunded")
            
            if amount and amount > payment.refundable_amount:
                raise serializers.ValidationError(
                    f"Refund amount cannot exceed {payment.refundable_amount}"
                )
            
            attrs['payment'] = payment
            if not amount:
                attrs['amount'] = payment.refundable_amount
            
        except Payment.DoesNotExist:
            raise serializers.ValidationError("Payment not found")
        
        return attrs


class PaymentMethodTokenizeSerializer(serializers.Serializer):
    """Serializer for tokenizing payment methods"""
    card_number = serializers.CharField()
    card_cvc = serializers.CharField()
    card_expiry = serializers.CharField()  # MM/YY format
    billing_address = serializers.JSONField(required=False)
    
    def validate_card_expiry(self, value):
        try:
            month, year = value.split('/')
            month = int(month)
            year = int('20' + year)
            
            if month < 1 or month > 12:
                raise serializers.ValidationError("Invalid month")
            
            if year < timezone.now().year:
                raise serializers.ValidationError("Card has expired")
                
        except (ValueError, IndexError):
            raise serializers.ValidationError("Invalid expiry format. Use MM/YY")
        
        return value


class PaymentStatsSerializer(serializers.Serializer):
    """Serializer for payment statistics"""
    total_payments = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    successful_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()
    pending_payments = serializers.IntegerField()
    total_refunds = serializers.IntegerField()
    refunded_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    active_subscriptions = serializers.IntegerField()
    total_disputes = serializers.IntegerField()
    open_disputes = serializers.IntegerField()


class WebhookValidationSerializer(serializers.Serializer):
    """Serializer for webhook validation"""
    provider_id = serializers.UUIDField()
    event_type = serializers.CharField()
    payload = serializers.JSONField()
    signature = serializers.CharField(required=False)
    timestamp = serializers.IntegerField(required=False)
