from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import requests
import json

from .models import (
    PaymentProvider, PaymentMethod, Payment, Refund, Subscription,
    Invoice, PaymentWebhook, PaymentDispute
)
from .serializers import (
    PaymentProviderSerializer, PaymentProviderCreateSerializer,
    PaymentMethodSerializer, PaymentMethodCreateSerializer,
    PaymentSerializer, PaymentCreateSerializer, PaymentUpdateSerializer,
    RefundSerializer, RefundCreateSerializer, SubscriptionSerializer,
    SubscriptionCreateSerializer, InvoiceSerializer, PaymentWebhookSerializer,
    PaymentDisputeSerializer, PaymentIntentSerializer, PaymentConfirmSerializer,
    RefundRequestSerializer, PaymentMethodTokenizeSerializer,
    PaymentStatsSerializer, WebhookValidationSerializer
)


class PaymentProviderListCreateView(generics.ListCreateAPIView):
    """List and create payment providers"""
    queryset = PaymentProvider.objects.all()
    serializer_class = PaymentProviderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['provider_type', 'is_active']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PaymentProviderCreateSerializer
        return PaymentProviderSerializer


class PaymentProviderDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Payment provider detail, update, delete"""
    queryset = PaymentProvider.objects.all()
    serializer_class = PaymentProviderSerializer
    permission_classes = [permissions.IsAuthenticated]


class PaymentMethodListCreateView(generics.ListCreateAPIView):
    """List and create payment methods"""
    queryset = PaymentMethod.objects.select_related('provider')
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['method_type', 'is_active', 'is_default']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PaymentMethodCreateSerializer
        return PaymentMethodSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset


class PaymentMethodDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Payment method detail, update, delete"""
    queryset = PaymentMethod.objects.select_related('provider')
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]


class PaymentListCreateView(generics.ListCreateAPIView):
    """List and create payments"""
    queryset = Payment.objects.select_related('provider', 'payment_method')
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'provider', 'currency']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PaymentCreateSerializer
        return PaymentSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by order
        order_id = self.request.query_params.get('order_id')
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        # Filter by amount range
        min_amount = self.request.query_params.get('min_amount')
        if min_amount:
            queryset = queryset.filter(amount__gte=min_amount)
        
        max_amount = self.request.query_params.get('max_amount')
        if max_amount:
            queryset = queryset.filter(amount__lte=max_amount)
        
        return queryset.order_by('-created_at')


class PaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Payment detail, update, delete"""
    queryset = Payment.objects.select_related('provider', 'payment_method')
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PaymentUpdateSerializer
        return PaymentSerializer


class PaymentIntentCreateView(APIView):
    """Create payment intent"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = PaymentIntentSerializer(data=request.data)
        
        if serializer.is_valid():
            # In a real implementation, this would call the payment provider API
            # For now, we'll create a mock payment intent
            payment_intent_data = {
                'id': f'pi_{timezone.now().strftime("%Y%m%d%H%M%S")}',
                'amount': serializer.validated_data['amount'],
                'currency': serializer.validated_data['currency'],
                'status': 'requires_payment_method',
                'client_secret': f'pi_{timezone.now().strftime("%Y%m%d%H%M%S")}_secret_{timezone.now().strftime("%Y%m%d%H%M%S")}'
            }
            
            return Response({
                'payment_intent': payment_intent_data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentConfirmView(APIView):
    """Confirm payment"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = PaymentConfirmSerializer(data=request.data)
        
        if serializer.is_valid():
            payment_intent_id = serializer.validated_data['payment_intent_id']
            
            # In a real implementation, this would confirm the payment with the provider
            # For now, we'll return a mock response
            return Response({
                'status': 'succeeded',
                'payment_intent_id': payment_intent_id,
                'message': 'Payment confirmed successfully'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RefundListCreateView(generics.ListCreateAPIView):
    """List and create refunds"""
    queryset = Refund.objects.select_related('payment')
    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'reason']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return RefundCreateSerializer
        return RefundSerializer


class RefundDetailView(generics.RetrieveAPIView):
    """Refund detail"""
    queryset = Refund.objects.select_related('payment')
    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAuthenticated]


class RefundRequestView(APIView):
    """Request a refund"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = RefundRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            payment = serializer.validated_data['payment']
            amount = serializer.validated_data['amount']
            reason = serializer.validated_data['reason']
            description = serializer.validated_data.get('description', '')
            
            with transaction.atomic():
                # Create refund record
                refund = Refund.objects.create(
                    payment=payment,
                    amount=amount,
                    currency=payment.currency,
                    reason=reason,
                    description=description
                )
                
                # Update payment refunded amount
                payment.refunded_amount += amount
                if payment.refunded_amount >= payment.amount:
                    payment.status = 'refunded'
                else:
                    payment.status = 'partially_refunded'
                payment.save()
            
            return Response({
                'message': 'Refund request created successfully',
                'refund': RefundSerializer(refund).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionListCreateView(generics.ListCreateAPIView):
    """List and create subscriptions"""
    queryset = Subscription.objects.select_related('provider', 'payment_method')
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'provider']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SubscriptionCreateSerializer
        return SubscriptionSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset


class SubscriptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Subscription detail, update, delete"""
    queryset = Subscription.objects.select_related('provider', 'payment_method')
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]


class InvoiceListView(generics.ListAPIView):
    """List invoices"""
    queryset = Invoice.objects.select_related('subscription', 'payment')
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'subscription']


class InvoiceDetailView(generics.RetrieveAPIView):
    """Invoice detail"""
    queryset = Invoice.objects.select_related('subscription', 'payment')
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]


class PaymentWebhookListView(generics.ListAPIView):
    """List payment webhooks"""
    queryset = PaymentWebhook.objects.select_related('provider')
    serializer_class = PaymentWebhookSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['provider', 'event_type', 'status']


class PaymentWebhookDetailView(generics.RetrieveAPIView):
    """Payment webhook detail"""
    queryset = PaymentWebhook.objects.select_related('provider')
    serializer_class = PaymentWebhookSerializer
    permission_classes = [permissions.IsAuthenticated]


class PaymentDisputeListView(generics.ListAPIView):
    """List payment disputes"""
    queryset = PaymentDispute.objects.select_related('payment')
    serializer_class = PaymentDisputeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'reason']


class PaymentDisputeDetailView(generics.RetrieveUpdateAPIView):
    """Payment dispute detail, update"""
    queryset = PaymentDispute.objects.select_related('payment')
    serializer_class = PaymentDisputeSerializer
    permission_classes = [permissions.IsAuthenticated]


class PaymentMethodTokenizeView(APIView):
    """Tokenize payment method"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = PaymentMethodTokenizeSerializer(data=request.data)
        
        if serializer.is_valid():
            # In a real implementation, this would tokenize the card with the payment provider
            # For now, we'll return a mock token
            card_number = serializer.validated_data['card_number']
            card_expiry = serializer.validated_data['card_expiry']
            
            # Mock tokenization
            token = f"tok_{timezone.now().strftime('%Y%m%d%H%M%S')}"
            
            return Response({
                'token': token,
                'card_last4': card_number[-4:],
                'card_brand': 'visa',  # Mock brand detection
                'exp_month': int(card_expiry.split('/')[0]),
                'exp_year': int('20' + card_expiry.split('/')[1])
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentStatsView(APIView):
    """Get payment statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        today = timezone.now().date()
        month_ago = today - timezone.timedelta(days=30)
        
        # Basic stats
        total_payments = Payment.objects.count()
        total_revenue = Payment.objects.filter(
            status__in=['succeeded', 'captured']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Status-based stats
        successful_payments = Payment.objects.filter(
            status__in=['succeeded', 'captured']
        ).count()
        failed_payments = Payment.objects.filter(status='failed').count()
        pending_payments = Payment.objects.filter(status='pending').count()
        
        # Refund stats
        total_refunds = Refund.objects.count()
        refunded_amount = Refund.objects.filter(
            status='succeeded'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Subscription stats
        active_subscriptions = Subscription.objects.filter(status='active').count()
        
        # Dispute stats
        total_disputes = PaymentDispute.objects.count()
        open_disputes = PaymentDispute.objects.filter(
            status__in=['needs_response', 'under_review', 'warning_needs_response']
        ).count()
        
        stats = {
            'total_payments': total_payments,
            'total_revenue': total_revenue,
            'successful_payments': successful_payments,
            'failed_payments': failed_payments,
            'pending_payments': pending_payments,
            'total_refunds': total_refunds,
            'refunded_amount': refunded_amount,
            'active_subscriptions': active_subscriptions,
            'total_disputes': total_disputes,
            'open_disputes': open_disputes,
        }
        
        serializer = PaymentStatsSerializer(stats)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WebhookReceiveView(APIView):
    """Receive webhooks from payment providers"""
    permission_classes = []  # No authentication for webhooks
    
    def post(self, request, provider_id):
        try:
            provider = PaymentProvider.objects.get(id=provider_id, is_active=True)
        except PaymentProvider.DoesNotExist:
            return Response({'error': 'Provider not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Validate webhook signature (in production)
        # signature = request.headers.get('Stripe-Signature')
        # if not self.verify_signature(request.body, signature, provider.webhook_secret):
        #     return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Process webhook
        try:
            event_type = request.data.get('type', 'unknown')
            
            webhook = PaymentWebhook.objects.create(
                provider=provider,
                event_type=event_type,
                provider_event_id=request.data.get('id', ''),
                raw_payload=request.data,
                status='pending'
            )
            
            # Process the webhook based on event type
            self.process_webhook(webhook, request.data)
            
            webhook.status = 'processed'
            webhook.processed_at = timezone.now()
            webhook.save()
            
            return Response({'status': 'success'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            if 'webhook' in locals():
                webhook.status = 'failed'
                webhook.error_message = str(e)
                webhook.save()
            
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def process_webhook(self, webhook, data):
        """Process webhook based on event type"""
        event_type = webhook.event_type
        
        if event_type == 'payment_intent.succeeded':
            self.handle_payment_succeeded(webhook, data)
        elif event_type == 'payment_intent.payment_failed':
            self.handle_payment_failed(webhook, data)
        elif event_type == 'charge.refunded':
            self.handle_refund_processed(webhook, data)
        elif event_type == 'charge.dispute.created':
            self.handle_dispute_created(webhook, data)
        # Add more event handlers as needed
    
    def handle_payment_succeeded(self, webhook, data):
        """Handle payment succeeded webhook"""
        payment_intent_id = data.get('data', {}).get('object', {}).get('id')
        if payment_intent_id:
            try:
                payment = Payment.objects.get(provider_intent_id=payment_intent_id)
                payment.status = 'succeeded'
                payment.captured_at = timezone.now()
                payment.save()
            except Payment.DoesNotExist:
                pass
    
    def handle_payment_failed(self, webhook, data):
        """Handle payment failed webhook"""
        payment_intent_id = data.get('data', {}).get('object', {}).get('id')
        if payment_intent_id:
            try:
                payment = Payment.objects.get(provider_intent_id=payment_intent_id)
                payment.status = 'failed'
                payment.failed_at = timezone.now()
                payment.save()
            except Payment.DoesNotExist:
                pass
    
    def handle_refund_processed(self, webhook, data):
        """Handle refund processed webhook"""
        charge_id = data.get('data', {}).get('object', {}).get('id')
        if charge_id:
            try:
                payment = Payment.objects.get(provider_charge_id=charge_id)
                refund_amount = data.get('data', {}).get('object', {}).get('amount_refunded', 0)
                
                # Update payment refunded amount
                payment.refunded_amount = Decimal(refund_amount) / 100  # Convert from cents
                if payment.refunded_amount >= payment.amount:
                    payment.status = 'refunded'
                else:
                    payment.status = 'partially_refunded'
                payment.save()
            except Payment.DoesNotExist:
                pass
    
    def handle_dispute_created(self, webhook, data):
        """Handle dispute created webhook"""
        charge_id = data.get('data', {}).get('object', {}).get('charge')
        if charge_id:
            try:
                payment = Payment.objects.get(provider_charge_id=charge_id)
                dispute_data = data.get('data', {}).get('object', {})
                
                PaymentDispute.objects.create(
                    payment=payment,
                    provider_dispute_id=dispute_data.get('id'),
                    amount=Decimal(dispute_data.get('amount', 0)) / 100,
                    currency=dispute_data.get('currency', 'USD'),
                    reason=dispute_data.get('reason', 'other'),
                    status='needs_response'
                )
                
                payment.status = 'disputed'
                payment.save()
            except Payment.DoesNotExist:
                pass


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def customer_payment_methods(request, customer_id):
    """Get payment methods for a customer"""
    payment_methods = PaymentMethod.objects.filter(
        customer_id=customer_id,
        is_active=True
    ).select_related('provider')
    
    serializer = PaymentMethodSerializer(payment_methods, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def customer_payments(request, customer_id):
    """Get payments for a customer"""
    payments = Payment.objects.filter(
        payment_method__customer_id=customer_id
    ).select_related('provider', 'payment_method')
    
    serializer = PaymentSerializer(payments, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def order_payments(request, order_id):
    """Get payments for an order"""
    payments = Payment.objects.filter(
        order_id=order_id
    ).select_related('provider', 'payment_method')
    
    serializer = PaymentSerializer(payments, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def cancel_subscription(request, pk):
    """Cancel a subscription"""
    try:
        subscription = Subscription.objects.get(pk=pk)
    except Subscription.DoesNotExist:
        return Response({'error': 'Subscription not found'}, status=status.HTTP_404_NOT_FOUND)
    
    subscription.status = 'canceled'
    subscription.canceled_at = timezone.now()
    subscription.save()
    
    return Response({
        'message': 'Subscription cancelled successfully',
        'subscription': SubscriptionSerializer(subscription).data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'service': 'payments',
        'timestamp': timezone.now().isoformat()
    }, status=status.HTTP_200_OK)
