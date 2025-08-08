from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, F
from django.utils import timezone

from .models import (
    Warehouse, InventoryItem, StockMovement, StockReservation,
    StockAlert, InventoryAudit, InventoryAuditItem
)
from .serializers import (
    WarehouseSerializer, InventoryItemSerializer, StockMovementSerializer,
    StockReservationSerializer, StockAlertSerializer, InventoryAuditSerializer,
    InventoryAuditItemSerializer, StockAdjustmentSerializer,
    StockReservationCreateSerializer, BulkStockUpdateSerializer,
    InventoryStatsSerializer
)
from .services import InventoryService


class WarehouseListCreateView(generics.ListCreateAPIView):
    """List and create warehouses"""
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']


class WarehouseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Warehouse detail, update, delete"""
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [permissions.IsAuthenticated]


class InventoryItemListCreateView(generics.ListCreateAPIView):
    """List and create inventory items"""
    queryset = InventoryItem.objects.select_related('warehouse')
    serializer_class = InventoryItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['warehouse', 'product_id']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by low stock
        if self.request.query_params.get('low_stock') == 'true':
            queryset = queryset.filter(quantity_available__lte=F('reorder_level'))
        
        # Filter by out of stock
        if self.request.query_params.get('out_of_stock') == 'true':
            queryset = queryset.filter(quantity_available=0)
        
        # Filter by SKU
        sku = self.request.query_params.get('sku')
        if sku:
            queryset = queryset.filter(sku__icontains=sku)
        
        return queryset


class InventoryItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Inventory item detail, update, delete"""
    queryset = InventoryItem.objects.select_related('warehouse')
    serializer_class = InventoryItemSerializer
    permission_classes = [permissions.IsAuthenticated]


class StockAdjustmentView(APIView):
    """Adjust stock levels"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = StockAdjustmentSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                movement = InventoryService.adjust_stock(
                    inventory_item=serializer.validated_data['inventory_item'],
                    adjustment_type=serializer.validated_data['adjustment_type'],
                    quantity=serializer.validated_data['quantity'],
                    reason=serializer.validated_data['reason'],
                    performed_by=str(request.user.id),
                    unit_cost=serializer.validated_data.get('unit_cost')
                )
                
                return Response({
                    'message': 'Stock adjusted successfully',
                    'movement': StockMovementSerializer(movement).data
                }, status=status.HTTP_200_OK)
                
            except ValueError as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StockReservationCreateView(APIView):
    """Create stock reservation"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = StockReservationCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                reservation = InventoryService.reserve_stock(
                    inventory_item=serializer.validated_data['inventory_item'],
                    quantity=serializer.validated_data['quantity'],
                    reference_type=serializer.validated_data['reference_type'],
                    reference_id=str(serializer.validated_data['reference_id']),
                    reserved_by=str(request.user.id),
                    expires_at=serializer.validated_data['expires_at']
                )
                
                return Response({
                    'message': 'Stock reserved successfully',
                    'reservation': StockReservationSerializer(reservation).data
                }, status=status.HTTP_201_CREATED)
                
            except ValueError as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StockReservationDetailView(generics.RetrieveAPIView):
    """Stock reservation detail"""
    queryset = StockReservation.objects.select_related('inventory_item__warehouse')
    serializer_class = StockReservationSerializer
    permission_classes = [permissions.IsAuthenticated]


class StockReservationConfirmView(APIView):
    """Confirm stock reservation"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            reservation = StockReservation.objects.get(pk=pk)
            movement = InventoryService.confirm_reservation(reservation)
            
            return Response({
                'message': 'Reservation confirmed successfully',
                'movement': StockMovementSerializer(movement).data
            }, status=status.HTTP_200_OK)
            
        except StockReservation.DoesNotExist:
            return Response({
                'error': 'Reservation not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class StockReservationReleaseView(APIView):
    """Release stock reservation"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            reservation = StockReservation.objects.get(pk=pk)
            movement = InventoryService.release_reservation(reservation)
            
            return Response({
                'message': 'Reservation released successfully',
                'movement': StockMovementSerializer(movement).data
            }, status=status.HTTP_200_OK)
            
        except StockReservation.DoesNotExist:
            return Response({
                'error': 'Reservation not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class StockMovementListView(generics.ListAPIView):
    """List stock movements"""
    queryset = StockMovement.objects.select_related('inventory_item__warehouse').order_by('-created_at')
    serializer_class = StockMovementSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['movement_type', 'inventory_item', 'reference_type']


class StockAlertListView(generics.ListAPIView):
    """List stock alerts"""
    queryset = StockAlert.objects.select_related('inventory_item__warehouse').order_by('-created_at')
    serializer_class = StockAlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['alert_type', 'status', 'inventory_item']


class StockAlertAcknowledgeView(APIView):
    """Acknowledge stock alert"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            alert = StockAlert.objects.get(pk=pk)
            alert.status = 'ACKNOWLEDGED'
            alert.acknowledged_by = str(request.user.id)
            alert.acknowledged_at = timezone.now()
            alert.save()
            
            return Response({
                'message': 'Alert acknowledged successfully'
            }, status=status.HTTP_200_OK)
            
        except StockAlert.DoesNotExist:
            return Response({
                'error': 'Alert not found'
            }, status=status.HTTP_404_NOT_FOUND)


class BulkStockUpdateView(APIView):
    """Bulk update stock levels"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = BulkStockUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                movements = InventoryService.bulk_update_stock(
                    serializer.validated_data['updates']
                )
                
                return Response({
                    'message': f'Successfully updated {len(movements)} items',
                    'movements': StockMovementSerializer(movements, many=True).data
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InventoryStatsView(APIView):
    """Get inventory statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        warehouse_id = request.query_params.get('warehouse_id')
        stats = InventoryService.get_inventory_stats(warehouse_id)
        
        serializer = InventoryStatsSerializer(stats)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def low_stock_items(request):
    """Get items with low stock"""
    items = InventoryItem.objects.filter(
        quantity_available__lte=F('reorder_level')
    ).select_related('warehouse')
    
    serializer = InventoryItemSerializer(items, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def out_of_stock_items(request):
    """Get items that are out of stock"""
    items = InventoryItem.objects.filter(
        quantity_available=0
    ).select_related('warehouse')
    
    serializer = InventoryItemSerializer(items, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def cleanup_expired_reservations(request):
    """Cleanup expired reservations (admin only)"""
    # Add admin check here if needed
    InventoryService.cleanup_expired_reservations()
    
    return Response({
        'message': 'Expired reservations cleaned up successfully'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'service': 'inventory',
        'timestamp': timezone.now().isoformat()
    }, status=status.HTTP_200_OK)