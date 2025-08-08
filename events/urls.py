from django.urls import path
from . import views

urlpatterns = [
    # Event management
    path('', views.EventListCreateView.as_view(), name='event-list-create'),
    path('<uuid:pk>/', views.EventDetailView.as_view(), name='event-detail'),
    path('search/', views.EventSearchView.as_view(), name='event-search'),
    path('stats/', views.EventStatsView.as_view(), name='event-stats'),
    
    # Event subscriptions
    path('subscriptions/', views.EventSubscriptionListCreateView.as_view(), name='subscription-list-create'),
    path('subscriptions/<uuid:pk>/', views.EventSubscriptionDetailView.as_view(), name='subscription-detail'),
    
    # Event deliveries
    path('deliveries/', views.EventDeliveryListView.as_view(), name='delivery-list'),
    path('deliveries/<uuid:pk>/', views.EventDeliveryDetailView.as_view(), name='delivery-detail'),
    
    # Event processing
    path('process/', views.EventProcessorView.as_view(), name='event-processor'),
    path('retry/', views.retry_failed_events, name='retry-failed-events'),
    path('cleanup/', views.cleanup_expired_events, name='cleanup-expired-events'),
    
    # Webhook endpoint
    path('webhook/', views.webhook_event_handler, name='webhook-event-handler'),
    
    # Health check
    path('health/', views.health_check, name='health-check'),
]
