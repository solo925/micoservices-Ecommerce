from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import requests

from .models import (
    Customer, Order, OrderItem, OrderHistory, ShippingMethod,
    Discount, Cart, CartItem
)
from .serializers import (
    CustomerSerializer, CustomerCreateSerializer, OrderSerializer,
    OrderCreateSerializer, OrderUpdateSerializer, OrderItemSerializer,
    OrderHistorySerializer, ShippingMethodSerializer, DiscountSerializer,
    CartSerializer, CartItemSerializer, CartItemCreateSerializer,
    CartItemUpdateSerializer, OrderStatusUpdateSerializer,
    PaymentStatusUpdateSerializer, FulfillmentStatusUpdateSerializer,
    OrderSearchSerializer, OrderStatsSerializer, DiscountValidationSerializer
)


class CustomerListCreateView(generics.ListCreateAPIView):
    """List and create customers"""
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['email', 'user_id']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CustomerCreateSerializer
        return CustomerSerializer


class CustomerDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Customer detail, update, delete"""
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]


class OrderListCreateView(generics.ListCreateAPIView):
    """List and create orders"""
    queryset = Order.objects.select_related('customer').prefetch_related('items', 'history')
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'payment_status', 'customer', 'created_at']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OrderCreateSerializer
        return OrderSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Search by order number
        order_number = self.request.query_params.get('order_number')
        if order_number:
            queryset = queryset.filter(order_number__icontains=order_number)
        
        # Search by customer email
        customer_email = self.request.query_params.get('customer_email')
        if customer_email:
            queryset = queryset.filter(customer_email__icontains=customer_email)
        
        # Date range filter
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        # Amount range filter
        min_amount = self.request.query_params.get('min_amount')
        if min_amount:
            queryset = queryset.filter(total_amount__gte=min_amount)
        
        max_amount = self.request.query_params.get('max_amount')
        if max_amount:
            queryset = queryset.filter(total_amount__lte=max_amount)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(
            user_id=str(self.request.user.id),
            user_name=self.request.user.get_full_name() or self.request.user.username
        )


class OrderDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Order detail, update, delete"""
    queryset = Order.objects.select_related('customer').prefetch_related('items', 'history')
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return OrderUpdateSerializer
        return OrderSerializer
    
    def perform_update(self, serializer):
        serializer.save(
            user_id=str(self.request.user.id),
            user_name=self.request.user.get_full_name() or self.request.user.username
        )


class OrderStatusUpdateView(APIView):
    """Update order status"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = OrderStatusUpdateSerializer(
            data=request.data,
            context={'order': order}
        )
        
        if serializer.is_valid():
            old_status = order.status
            new_status = serializer.validated_data['status']
            notes = serializer.validated_data.get('notes', '')
            
            with transaction.atomic():
                order.status = new_status
                order.save()
                
                # Create history entry
                OrderHistory.objects.create(
                    order=order,
                    event_type='status_changed',
                    description=f'Order status changed from {old_status} to {new_status}. {notes}',
                    old_value=old_status,
                    new_value=new_status,
                    user_id=str(request.user.id),
                    user_name=request.user.get_full_name() or request.user.username
                )
                
                # Update timestamps based on status
                if new_status == 'confirmed':
                    order.confirmed_at = timezone.now()
                elif new_status == 'shipped':
                    order.shipped_at = timezone.now()
                elif new_status == 'delivered':
                    order.delivered_at = timezone.now()
                elif new_status == 'cancelled':
                    order.cancelled_at = timezone.now()
                
                order.save()
            
            return Response({
                'message': f'Order status updated to {new_status}',
                'order': OrderSerializer(order).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentStatusUpdateView(APIView):
    """Update payment status"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = PaymentStatusUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            old_payment_status = order.payment_status
            new_payment_status = serializer.validated_data['payment_status']
            
            with transaction.atomic():
                order.payment_status = new_payment_status
                
                # Update payment details
                if 'payment_transaction_id' in serializer.validated_data:
                    order.payment_transaction_id = serializer.validated_data['payment_transaction_id']
                if 'payment_gateway' in serializer.validated_data:
                    order.payment_gateway = serializer.validated_data['payment_gateway']
                
                order.save()
                
                # Create history entry
                event_type = 'payment_received' if new_payment_status == 'paid' else 'status_changed'
                OrderHistory.objects.create(
                    order=order,
                    event_type=event_type,
                    description=f'Payment status changed from {old_payment_status} to {new_payment_status}',
                    old_value=old_payment_status,
                    new_value=new_payment_status,
                    user_id=str(request.user.id),
                    user_name=request.user.get_full_name() or request.user.username
                )
            
            return Response({
                'message': f'Payment status updated to {new_payment_status}',
                'order': OrderSerializer(order).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FulfillmentStatusUpdateView(APIView):
    """Update fulfillment status"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = FulfillmentStatusUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            with transaction.atomic():
                # Update fulfillment details
                if 'tracking_number' in serializer.validated_data:
                    order.tracking_number = serializer.validated_data['tracking_number']
                if 'shipping_carrier' in serializer.validated_data:
                    order.shipping_carrier = serializer.validated_data['shipping_carrier']
                if 'estimated_delivery' in serializer.validated_data:
                    order.estimated_delivery = serializer.validated_data['estimated_delivery']
                
                order.fulfillment_status = serializer.validated_data['fulfillment_status']
                order.save()
                
                # Create history entry
                OrderHistory.objects.create(
                    order=order,
                    event_type='shipped' if serializer.validated_data['fulfillment_status'] == 'fulfilled' else 'status_changed',
                    description=f'Fulfillment status updated to {serializer.validated_data["fulfillment_status"]}',
                    new_value=serializer.validated_data['fulfillment_status'],
                    user_id=str(request.user.id),
                    user_name=request.user.get_full_name() or request.user.username
                )
            
            return Response({
                'message': f'Fulfillment status updated',
                'order': OrderSerializer(order).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OrderHistoryListView(generics.ListAPIView):
    """List order history"""
    serializer_class = OrderHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        order_id = self.kwargs.get('order_id')
        return OrderHistory.objects.filter(order_id=order_id).order_by('-created_at')


class ShippingMethodListView(generics.ListAPIView):
    """List available shipping methods"""
    queryset = ShippingMethod.objects.filter(is_active=True)
    serializer_class = ShippingMethodSerializer
    permission_classes = [permissions.IsAuthenticated]


class DiscountListView(generics.ListAPIView):
    """List active discounts"""
    queryset = Discount.objects.filter(is_active=True)
    serializer_class = DiscountSerializer
    permission_classes = [permissions.IsAuthenticated]


class DiscountValidationView(APIView):
    """Validate discount code"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = DiscountValidationSerializer(data=request.data)
        
        if serializer.is_valid():
            discount = serializer.validated_data['discount']
            order_amount = serializer.validated_data['order_amount']
            
            # Calculate discount amount
            if discount.discount_type == 'percentage':
                discount_amount = order_amount * (discount.discount_value / 100)
                if discount.max_discount_amount:
                    discount_amount = min(discount_amount, discount.max_discount_amount)
            elif discount.discount_type == 'fixed_amount':
                discount_amount = discount.discount_value
            else:  # free_shipping
                discount_amount = Decimal('0.00')  # Will be handled separately
            
            return Response({
                'valid': True,
                'discount': DiscountSerializer(discount).data,
                'discount_amount': discount_amount,
                'final_amount': order_amount - discount_amount
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CartDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Cart detail and management"""
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        customer = Customer.objects.filter(user_id=self.request.user.id).first()
        if not customer:
            return None
        
        cart, created = Cart.objects.get_or_create(
            customer=customer,
            defaults={'expires_at': timezone.now() + timezone.timedelta(days=7)}
        )
        return cart


class CartItemCreateView(generics.CreateAPIView):
    """Add item to cart"""
    serializer_class = CartItemCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        customer = Customer.objects.filter(user_id=self.request.user.id).first()
        if customer:
            cart, created = Cart.objects.get_or_create(
                customer=customer,
                defaults={'expires_at': timezone.now() + timezone.timedelta(days=7)}
            )
            context['cart'] = cart
        return context


class CartItemUpdateView(generics.UpdateDestroyAPIView):
    """Update or remove cart item"""
    serializer_class = CartItemUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        customer = Customer.objects.filter(user_id=self.request.user.id).first()
        if customer:
            return CartItem.objects.filter(cart__customer=customer)
        return CartItem.objects.none()


class OrderStatsView(APIView):
    """Get order statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        today = timezone.now().date()
        week_ago = today - timezone.timedelta(days=7)
        month_ago = today - timezone.timedelta(days=30)
        
        # Basic stats
        total_orders = Order.objects.count()
        total_revenue = Order.objects.filter(
            payment_status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        # Time-based stats
        orders_today = Order.objects.filter(created_at__date=today).count()
        orders_this_week = Order.objects.filter(created_at__date__gte=week_ago).count()
        orders_this_month = Order.objects.filter(created_at__date__gte=month_ago).count()
        
        # Status-based stats
        pending_orders = Order.objects.filter(status='pending').count()
        processing_orders = Order.objects.filter(status='processing').count()
        shipped_orders = Order.objects.filter(status='shipped').count()
        cancelled_orders = Order.objects.filter(status='cancelled').count()
        
        # Average order value
        avg_order_value = Order.objects.filter(
            payment_status='paid'
        ).aggregate(avg=Avg('total_amount'))['avg'] or Decimal('0.00')
        
        stats = {
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'average_order_value': avg_order_value,
            'orders_today': orders_today,
            'orders_this_week': orders_this_week,
            'orders_this_month': orders_this_month,
            'pending_orders': pending_orders,
            'processing_orders': processing_orders,
            'shipped_orders': shipped_orders,
            'cancelled_orders': cancelled_orders,
        }
        
        serializer = OrderStatsSerializer(stats)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderSearchView(APIView):
    """Advanced order search"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = OrderSearchSerializer(data=request.data)
        
        if serializer.is_valid():
            queryset = Order.objects.select_related('customer').prefetch_related('items')
            
            # Apply filters
            if serializer.validated_data.get('order_number'):
                queryset = queryset.filter(
                    order_number__icontains=serializer.validated_data['order_number']
                )
            
            if serializer.validated_data.get('customer_email'):
                queryset = queryset.filter(
                    customer_email__icontains=serializer.validated_data['customer_email']
                )
            
            if serializer.validated_data.get('status'):
                queryset = queryset.filter(status=serializer.validated_data['status'])
            
            if serializer.validated_data.get('payment_status'):
                queryset = queryset.filter(payment_status=serializer.validated_data['payment_status'])
            
            if serializer.validated_data.get('date_from'):
                queryset = queryset.filter(created_at__date__gte=serializer.validated_data['date_from'])
            
            if serializer.validated_data.get('date_to'):
                queryset = queryset.filter(created_at__date__lte=serializer.validated_data['date_to'])
            
            if serializer.validated_data.get('min_amount'):
                queryset = queryset.filter(total_amount__gte=serializer.validated_data['min_amount'])
            
            if serializer.validated_data.get('max_amount'):
                queryset = queryset.filter(total_amount__lte=serializer.validated_data['max_amount'])
            
            orders = queryset.order_by('-created_at')
            serializer = OrderSerializer(orders, many=True)
            
            return Response({
                'count': orders.count(),
                'results': serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def customer_orders(request, customer_id):
    """Get orders for a specific customer"""
    try:
        customer = Customer.objects.get(id=customer_id)
        orders = Order.objects.filter(customer=customer).order_by('-created_at')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Customer.DoesNotExist:
        return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def cancel_order(request, pk):
    """Cancel an order"""
    try:
        order = Order.objects.get(pk=pk)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if not order.can_cancel:
        return Response({'error': 'Order cannot be cancelled'}, status=status.HTTP_400_BAD_REQUEST)
    
    with transaction.atomic():
        order.status = 'cancelled'
        order.cancelled_at = timezone.now()
        order.save()
        
        # Create history entry
        OrderHistory.objects.create(
            order=order,
            event_type='cancelled',
            description='Order cancelled',
            user_id=str(request.user.id),
            user_name=request.user.get_full_name() or request.user.username
        )
        
        # Release inventory reservations
        for item in order.items.all():
            if item.inventory_item_id:
                # Call inventory service to release reservation
                try:
                    # This would be a call to the inventory service
                    # For now, we'll just log it
                    print(f"Releasing inventory reservation for item {item.inventory_item_id}")
                except Exception as e:
                    print(f"Error releasing inventory: {e}")
    
    return Response({
        'message': 'Order cancelled successfully',
        'order': OrderSerializer(order).data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'service': 'orders',
        'timestamp': timezone.now().isoformat()
    }, status=status.HTTP_200_OK)
