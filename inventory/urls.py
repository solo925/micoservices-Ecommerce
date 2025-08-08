from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Warehouse endpoints
    path('warehouses/', views.WarehouseListCreateView.as_view(), name='warehouse-list'),
    path('warehouses/<uuid:pk>/', views.WarehouseDetailView.as_view(), name='warehouse-detail'),
    
    # Inventory items endpoints
    path('items/', views.InventoryItemListCreateView.as_view(), name='inventory-list'),
    path('items/<uuid:pk>/', views.InventoryItemDetailView.as_view(), name='inventory-detail'),
    
    # Stock operations
    path('adjust/', views.StockAdjustmentView.as_view(), name='stock-adjust'),
    path('bulk-update/', views.BulkStockUpdateView.as_view(), name='bulk-update'),
    
    # Reservations
    path('reservations/', views.StockReservationCreateView.as_view(), name='reservation-create'),
    path('reservations/<uuid:pk>/', views.StockReservationDetailView.as_view(), name='reservation-detail'),
    path('reservations/<uuid:pk>/confirm/', views.StockReservationConfirmView.as_view(), name='reservation-confirm'),
    path('reservations/<uuid:pk>/release/', views.StockReservationReleaseView.as_view(), name='reservation-release'),
    
    # Stock movements
    path('movements/', views.StockMovementListView.as_view(), name='movement-list'),
    
    # Alerts
    path('alerts/', views.StockAlertListView.as_view(), name='alert-list'),
    path('alerts/<uuid:pk>/acknowledge/', views.StockAlertAcknowledgeView.as_view(), name='alert-acknowledge'),
    
    # Reports and stats
    path('stats/', views.InventoryStatsView.as_view(), name='inventory-stats'),
    path('low-stock/', views.low_stock_items, name='low-stock'),
    path('out-of-stock/', views.out_of_stock_items, name='out-of-stock'),
    
    # Maintenance
    path('cleanup-reservations/', views.cleanup_expired_reservations, name='cleanup-reservations'),
    
    # Health check
    path('health/', views.health_check, name='health-check'),
]
