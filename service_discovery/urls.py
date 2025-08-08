from django.urls import path
from . import views

urlpatterns = [
    # Service Registry
    path('services/', views.ServiceRegistryListCreateView.as_view(), name='service-registry-list-create'),
    path('services/<uuid:id>/', views.ServiceRegistryDetailView.as_view(), name='service-registry-detail'),
    path('services/search/', views.ServiceSearchView.as_view(), name='service-search'),
    
    # Service Instances
    path('instances/', views.ServiceInstanceListCreateView.as_view(), name='service-instance-list-create'),
    path('instances/<uuid:id>/', views.ServiceInstanceDetailView.as_view(), name='service-instance-detail'),
    
    # Health Checks
    path('health-checks/', views.HealthCheckListView.as_view(), name='health-check-list'),
    path('health-checks/<uuid:id>/', views.HealthCheckDetailView.as_view(), name='health-check-detail'),
    path('health-checks/perform/', views.perform_health_checks, name='perform-health-checks'),
    path('health-checks/perform-single/', views.perform_health_check, name='perform-health-check'),
    
    # Configurations
    path('configurations/', views.ConfigurationListCreateView.as_view(), name='configuration-list-create'),
    path('configurations/<uuid:id>/', views.ConfigurationDetailView.as_view(), name='configuration-detail'),
    path('configurations/search/', views.ConfigurationSearchView.as_view(), name='configuration-search'),
    path('configurations/get/', views.get_configuration, name='get-configuration'),
    path('configurations/set/', views.set_configuration, name='set-configuration'),
    path('configurations/bulk-update/', views.bulk_update_configurations, name='bulk-update-configurations'),
    
    # Configuration History
    path('configuration-history/', views.ConfigurationHistoryListView.as_view(), name='configuration-history-list'),
    path('configuration-history/<uuid:id>/', views.ConfigurationHistoryDetailView.as_view(), name='configuration-history-detail'),
    
    # Service Dependencies
    path('dependencies/', views.ServiceDependencyListCreateView.as_view(), name='service-dependency-list-create'),
    path('dependencies/<uuid:id>/', views.ServiceDependencyDetailView.as_view(), name='service-dependency-detail'),
    
    # Service Metrics
    path('metrics/', views.ServiceMetricsListCreateView.as_view(), name='service-metrics-list-create'),
    path('metrics/<uuid:id>/', views.ServiceMetricsDetailView.as_view(), name='service-metrics-detail'),
    
    # Service Registration and Heartbeat
    path('register/', views.service_registration, name='service-registration'),
    path('heartbeat/', views.service_heartbeat, name='service-heartbeat'),
    path('deregister/', views.service_deregistration, name='service-deregistration'),
    
    # Health Summary and Statistics
    path('health-summary/', views.ServiceHealthSummaryView.as_view(), name='service-health-summary'),
    path('stats/', views.ServiceDiscoveryStatsView.as_view(), name='service-discovery-stats'),
    
    # Health Check Endpoint
    path('health/', views.health_check, name='health-check'),
]
