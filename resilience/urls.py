from django.urls import path
from . import views

urlpatterns = [
    # Resilience metrics and management
    path('metrics/', views.ResilienceMetricsView.as_view(), name='resilience-metrics'),
    path('health/', views.resilience_health_check, name='resilience-health'),
    path('dashboard/', views.resilience_dashboard_data, name='resilience-dashboard'),
    path('reset/', views.reset_all_resilience, name='reset-resilience'),
    
    # Circuit breaker management
    path('circuit-breakers/', views.CircuitBreakerManagementView.as_view(), name='circuit-breakers'),
    path('circuit-breakers/<str:name>/', views.CircuitBreakerDetailView.as_view(), name='circuit-breaker-detail'),
    
    # Bulkhead management
    path('bulkheads/', views.BulkheadManagementView.as_view(), name='bulkheads'),
    
    # Chaos engineering
    path('chaos/', views.ChaosEngineeringView.as_view(), name='chaos-engineering'),
]
