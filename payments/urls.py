from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment providers
    path('providers/', views.PaymentProviderListCreateView.as_view(), name='provider-list'),
    path('providers/<uuid:pk>/', views.PaymentProviderDetailView.as_view(), name='provider-detail'),
    
    # Payment methods
    path('methods/', views.PaymentMethodListCreateView.as_view(), name='method-list'),
    path('methods/<uuid:pk>/', views.PaymentMethodDetailView.as_view(), name='method-detail'),
    path('methods/tokenize/', views.PaymentMethodTokenizeView.as_view(), name='method-tokenize'),
    path('customers/<uuid:customer_id>/methods/', views.customer_payment_methods, name='customer-methods'),
    
    # Payments
    path('', views.PaymentListCreateView.as_view(), name='payment-list'),
    path('<uuid:pk>/', views.PaymentDetailView.as_view(), name='payment-detail'),
    path('intent/', views.PaymentIntentCreateView.as_view(), name='payment-intent'),
    path('confirm/', views.PaymentConfirmView.as_view(), name='payment-confirm'),
    path('customers/<uuid:customer_id>/payments/', views.customer_payments, name='customer-payments'),
    path('orders/<uuid:order_id>/payments/', views.order_payments, name='order-payments'),
    
    # Refunds
    path('refunds/', views.RefundListCreateView.as_view(), name='refund-list'),
    path('refunds/<uuid:pk>/', views.RefundDetailView.as_view(), name='refund-detail'),
    path('refunds/request/', views.RefundRequestView.as_view(), name='refund-request'),
    
    # Subscriptions
    path('subscriptions/', views.SubscriptionListCreateView.as_view(), name='subscription-list'),
    path('subscriptions/<uuid:pk>/', views.SubscriptionDetailView.as_view(), name='subscription-detail'),
    path('subscriptions/<uuid:pk>/cancel/', views.cancel_subscription, name='subscription-cancel'),
    
    # Invoices
    path('invoices/', views.InvoiceListView.as_view(), name='invoice-list'),
    path('invoices/<uuid:pk>/', views.InvoiceDetailView.as_view(), name='invoice-detail'),
    
    # Webhooks
    path('webhooks/', views.PaymentWebhookListView.as_view(), name='webhook-list'),
    path('webhooks/<uuid:pk>/', views.PaymentWebhookDetailView.as_view(), name='webhook-detail'),
    path('webhooks/<uuid:provider_id>/receive/', views.WebhookReceiveView.as_view(), name='webhook-receive'),
    
    # Disputes
    path('disputes/', views.PaymentDisputeListView.as_view(), name='dispute-list'),
    path('disputes/<uuid:pk>/', views.PaymentDisputeDetailView.as_view(), name='dispute-detail'),
    
    # Statistics
    path('stats/', views.PaymentStatsView.as_view(), name='payment-stats'),
    
    # Health check
    path('health/', views.health_check, name='health-check'),
]
