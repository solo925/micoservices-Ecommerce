from django.urls import path
from . import views

urlpatterns = [
    # Order processing with SAGA
    path('order/', views.OrderSagaView.as_view(), name='saga-order'),
    
    # Saga management
    path('status/<str:saga_id>/', views.SagaStatusView.as_view(), name='saga-status'),
    path('list/', views.SagaListView.as_view(), name='saga-list'),
    path('metrics/', views.saga_metrics, name='saga-metrics'),
    
    # Testing and monitoring
    path('test/', views.test_saga_patterns, name='saga-test'),
    path('health/', views.saga_health_check, name='saga-health'),
]
