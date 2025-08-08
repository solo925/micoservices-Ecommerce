from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    # Audit Log URLs
    path('logs/', views.AuditLogListCreateView.as_view(), name='audit_log_list_create'),
    path('logs/<uuid:id>/', views.AuditLogDetailView.as_view(), name='audit_log_detail'),
    path('logs/search/', views.AuditLogSearchView.as_view(), name='audit_log_search'),
    path('logs/stats/', views.AuditLogStatsView.as_view(), name='audit_log_stats'),
    
    # Security Event URLs
    path('security-events/', views.SecurityEventListCreateView.as_view(), name='security_event_list_create'),
    path('security-events/<uuid:id>/', views.SecurityEventDetailView.as_view(), name='security_event_detail'),
    path('security-events/search/', views.SecurityEventSearchView.as_view(), name='security_event_search'),
    path('security-events/stats/', views.SecurityEventStatsView.as_view(), name='security_event_stats'),
    
    # Performance Metric URLs
    path('performance-metrics/', views.PerformanceMetricListCreateView.as_view(), name='performance_metric_list_create'),
    path('performance-metrics/<uuid:id>/', views.PerformanceMetricDetailView.as_view(), name='performance_metric_detail'),
    path('performance-metrics/search/', views.PerformanceMetricSearchView.as_view(), name='performance_metric_search'),
    path('performance-metrics/stats/', views.PerformanceMetricStatsView.as_view(), name='performance_metric_stats'),
    
    # Data Change Log URLs
    path('data-changes/', views.DataChangeLogListCreateView.as_view(), name='data_change_log_list_create'),
    path('data-changes/<uuid:id>/', views.DataChangeLogDetailView.as_view(), name='data_change_log_detail'),
    path('data-changes/search/', views.DataChangeLogSearchView.as_view(), name='data_change_log_search'),
    path('data-changes/history/<uuid:object_id>/<int:content_type_id>/', views.DataChangeHistoryView.as_view(), name='data_change_history'),
    
    # API Audit Log URLs
    path('api-logs/', views.APIAuditLogListCreateView.as_view(), name='api_audit_log_list_create'),
    path('api-logs/<uuid:id>/', views.APIAuditLogDetailView.as_view(), name='api_audit_log_detail'),
    path('api-logs/search/', views.APIAuditLogSearchView.as_view(), name='api_audit_log_search'),
    path('api-logs/stats/', views.APIAuditLogStatsView.as_view(), name='api_audit_log_stats'),
    
    # Distributed Trace URLs
    path('traces/', views.DistributedTraceListCreateView.as_view(), name='distributed_trace_list_create'),
    path('traces/<uuid:id>/', views.DistributedTraceDetailView.as_view(), name='distributed_trace_detail'),
    path('traces/search/', views.DistributedTraceSearchView.as_view(), name='distributed_trace_search'),
    path('traces/<uuid:trace_id>/tree/', views.DistributedTraceTreeView.as_view(), name='distributed_trace_tree'),
    path('traces/stats/', views.DistributedTraceStatsView.as_view(), name='distributed_trace_stats'),
    
    # Audit Configuration URLs
    path('configurations/', views.AuditConfigurationListCreateView.as_view(), name='audit_configuration_list_create'),
    path('configurations/<uuid:id>/', views.AuditConfigurationDetailView.as_view(), name='audit_configuration_detail'),
    
    # Utility URLs
    path('start-trace/', views.StartTraceView.as_view(), name='start_trace'),
    path('end-trace/', views.EndTraceView.as_view(), name='end_trace'),
    path('record-metric/', views.RecordMetricView.as_view(), name='record_metric'),
    path('log-security-event/', views.LogSecurityEventView.as_view(), name='log_security_event'),
    path('log-api-call/', views.LogAPICallView.as_view(), name='log_api_call'),
    
    # Health Check
    path('health/', views.health_check, name='health_check'),
]
