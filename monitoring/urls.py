from django.urls import path
from . import views

urlpatterns = [
    path('metrics/', views.prometheus_metrics, name='prometheus-metrics'),
    path('health/', views.health_check, name='health-check'),
    path('business/', views.business_metrics, name='business-metrics'),
    path('performance/', views.performance_metrics, name='performance-metrics'),
    path('tracing/', views.tracing_info, name='tracing-info'),
]
