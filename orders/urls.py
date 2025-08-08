from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Customer endpoints
    path('customers/', views.CustomerListCreateView.as_view(), name='customer-list'),
    path('customers/<uuid:pk>/', views.CustomerDetailView.as_view(), name='customer-detail'),
    path('customers/<uuid:customer_id>/orders/', views.customer_orders, name='customer-orders'),
    
    # Order endpoints
    path('', views.OrderListCreateView.as_view(), name='order-list'),
    path('<uuid:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('<uuid:pk>/status/', views.OrderStatusUpdateView.as_view(), name='order-status-update'),
    path('<uuid:pk>/payment/', views.PaymentStatusUpdateView.as_view(), name='payment-status-update'),
    path('<uuid:pk>/fulfillment/', views.FulfillmentStatusUpdateView.as_view(), name='fulfillment-status-update'),
    path('<uuid:pk>/cancel/', views.cancel_order, name='cancel-order'),
    path('<uuid:order_id>/history/', views.OrderHistoryListView.as_view(), name='order-history'),
    
    # Shipping and discounts
    path('shipping-methods/', views.ShippingMethodListView.as_view(), name='shipping-methods'),
    path('discounts/', views.DiscountListView.as_view(), name='discounts'),
    path('discounts/validate/', views.DiscountValidationView.as_view(), name='discount-validation'),
    
    # Cart endpoints
    path('cart/', views.CartDetailView.as_view(), name='cart-detail'),
    path('cart/items/', views.CartItemCreateView.as_view(), name='cart-item-create'),
    path('cart/items/<uuid:pk>/', views.CartItemUpdateView.as_view(), name='cart-item-update'),
    
    # Reports and stats
    path('stats/', views.OrderStatsView.as_view(), name='order-stats'),
    path('search/', views.OrderSearchView.as_view(), name='order-search'),
    
    # Health check
    path('health/', views.health_check, name='health-check'),
]
