from django.urls import path, re_path
from . import views

urlpatterns = [
    # GraphQL endpoint
    path('graphql/', views.GraphQLView.as_view(), name='graphql'),
    
    # Service proxy endpoints
    re_path(r'^proxy/(?P<service_name>[\w-]+)/(?P<path>.*)/$', views.ServiceProxyView.as_view(), name='service-proxy'),
    path('proxy/<str:service_name>/', views.ServiceProxyView.as_view(), name='service-proxy-root'),
    
    # Gateway management
    path('stats/', views.GatewayStatsView.as_view(), name='gateway-stats'),
    path('config/', views.LoadBalancerConfigView.as_view(), name='load-balancer-config'),
    
    # Health check
    path('health/', views.health_check, name='health_check'),
]
