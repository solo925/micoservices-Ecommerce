from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/products/', include('products.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/gateway/', include('gateway.urls')),
    path('api/notification/', include('notification.urls')),
    path('api/audit/', include('audit.urls')),
    path('api/events/', include('events.urls')),
    path('api/service-discovery/', include('service_discovery.urls')),
    path('api/metrics/', include('monitoring.urls')),
    path('api/resilience/', include('resilience.urls')),
    path('api/saga/', include('saga.urls')),
    path('prometheus/', include('monitoring.urls'))
]
