import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from .models import (
    ServiceRegistry, ServiceInstance, HealthCheck, Configuration,
    ConfigurationHistory, ServiceDependency, ServiceMetrics
)
from .services import (
    ServiceRegistryService, HealthCheckService, ConfigurationService,
    ServiceMetricsService, ServiceDiscoveryStatsService
)
from .serializers import (
    ServiceRegistrySerializer, ServiceRegistryCreateSerializer, ServiceRegistryUpdateSerializer,
    ServiceInstanceSerializer, ServiceInstanceCreateSerializer, ServiceInstanceUpdateSerializer,
    HealthCheckSerializer, HealthCheckCreateSerializer,
    ConfigurationSerializer, ConfigurationCreateSerializer, ConfigurationUpdateSerializer,
    ConfigurationHistorySerializer, ServiceDependencySerializer, ServiceDependencyCreateSerializer,
    ServiceMetricsSerializer, ServiceMetricsCreateSerializer,
    ServiceRegistryListSerializer, ServiceInstanceListSerializer, ConfigurationListSerializer,
    ServiceHealthSummarySerializer, ServiceDiscoveryStatsSerializer,
    ConfigurationSearchSerializer, ServiceSearchSerializer,
    ServiceRegistrationSerializer, ServiceHeartbeatSerializer, ConfigurationBulkUpdateSerializer
)


# Service Registry Views
class ServiceRegistryListCreateView(generics.ListCreateAPIView):
    """List and create service registries"""
    queryset = ServiceRegistry.objects.all()
    serializer_class = ServiceRegistrySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['service_type', 'status', 'environment', 'is_public']
    search_fields = ['service_name', 'description']
    ordering_fields = ['service_name', 'created_at', 'last_heartbeat']
    ordering = ['service_name']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ServiceRegistryCreateSerializer
        return ServiceRegistryListSerializer


class ServiceRegistryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete service registry"""
    queryset = ServiceRegistry.objects.all()
    serializer_class = ServiceRegistrySerializer
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ServiceRegistryUpdateSerializer
        return ServiceRegistrySerializer


# Service Instance Views
class ServiceInstanceListCreateView(generics.ListCreateAPIView):
    """List and create service instances"""
    queryset = ServiceInstance.objects.select_related('service')
    serializer_class = ServiceInstanceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['service', 'status', 'is_primary']
    search_fields = ['instance_id', 'host']
    ordering_fields = ['instance_id', 'created_at', 'last_heartbeat']
    ordering = ['service', 'instance_id']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ServiceInstanceCreateSerializer
        return ServiceInstanceListSerializer


class ServiceInstanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete service instance"""
    queryset = ServiceInstance.objects.select_related('service')
    serializer_class = ServiceInstanceSerializer
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ServiceInstanceUpdateSerializer
        return ServiceInstanceSerializer


# Health Check Views
class HealthCheckListView(generics.ListAPIView):
    """List health checks"""
    queryset = HealthCheck.objects.select_related('service_instance__service')
    serializer_class = HealthCheckSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['service_instance', 'status']
    ordering_fields = ['checked_at', 'response_time_ms']
    ordering = ['-checked_at']


class HealthCheckDetailView(generics.RetrieveAPIView):
    """Retrieve health check details"""
    queryset = HealthCheck.objects.select_related('service_instance__service')
    serializer_class = HealthCheckSerializer
    lookup_field = 'id'


# Configuration Views
class ConfigurationListCreateView(generics.ListCreateAPIView):
    """List and create configurations"""
    queryset = Configuration.objects.all()
    serializer_class = ConfigurationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['config_type', 'service_name', 'environment', 'is_sensitive']
    search_fields = ['key', 'description']
    ordering_fields = ['key', 'updated_at']
    ordering = ['key']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ConfigurationCreateSerializer
        return ConfigurationListSerializer


class ConfigurationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete configuration"""
    queryset = Configuration.objects.all()
    serializer_class = ConfigurationSerializer
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ConfigurationUpdateSerializer
        return ConfigurationSerializer


# Configuration History Views
class ConfigurationHistoryListView(generics.ListAPIView):
    """List configuration history"""
    queryset = ConfigurationHistory.objects.select_related('configuration')
    serializer_class = ConfigurationHistorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['configuration', 'change_type']
    ordering_fields = ['changed_at']
    ordering = ['-changed_at']


class ConfigurationHistoryDetailView(generics.RetrieveAPIView):
    """Retrieve configuration history details"""
    queryset = ConfigurationHistory.objects.select_related('configuration')
    serializer_class = ConfigurationHistorySerializer
    lookup_field = 'id'


# Service Dependency Views
class ServiceDependencyListCreateView(generics.ListCreateAPIView):
    """List and create service dependencies"""
    queryset = ServiceDependency.objects.select_related('source_service', 'target_service')
    serializer_class = ServiceDependencySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['source_service', 'target_service', 'dependency_type', 'is_active']
    ordering_fields = ['created_at']
    ordering = ['source_service', 'target_service']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ServiceDependencyCreateSerializer
        return ServiceDependencySerializer


class ServiceDependencyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete service dependency"""
    queryset = ServiceDependency.objects.select_related('source_service', 'target_service')
    serializer_class = ServiceDependencySerializer
    lookup_field = 'id'


# Service Metrics Views
class ServiceMetricsListCreateView(generics.ListCreateAPIView):
    """List and create service metrics"""
    queryset = ServiceMetrics.objects.select_related('service_instance__service')
    serializer_class = ServiceMetricsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['service_instance']
    ordering_fields = ['recorded_at']
    ordering = ['-recorded_at']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ServiceMetricsCreateSerializer
        return ServiceMetricsSerializer


class ServiceMetricsDetailView(generics.RetrieveAPIView):
    """Retrieve service metrics details"""
    queryset = ServiceMetrics.objects.select_related('service_instance__service')
    serializer_class = ServiceMetricsSerializer
    lookup_field = 'id'


# Specialized Views
class ServiceSearchView(APIView):
    """Search services with advanced filters"""
    
    def post(self, request):
        serializer = ServiceSearchSerializer(data=request.data)
        if serializer.is_valid():
            filters = Q()
            
            if serializer.validated_data.get('service_name'):
                filters &= Q(service_name__icontains=serializer.validated_data['service_name'])
            
            if serializer.validated_data.get('service_type'):
                filters &= Q(service_type=serializer.validated_data['service_type'])
            
            if serializer.validated_data.get('status'):
                filters &= Q(status=serializer.validated_data['status'])
            
            if serializer.validated_data.get('environment'):
                filters &= Q(environment=serializer.validated_data['environment'])
            
            if serializer.validated_data.get('is_public') is not None:
                filters &= Q(is_public=serializer.validated_data['is_public'])
            
            services = ServiceRegistry.objects.filter(filters)
            serializer = ServiceRegistryListSerializer(services, many=True)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ConfigurationSearchView(APIView):
    """Search configurations with advanced filters"""
    
    def post(self, request):
        serializer = ConfigurationSearchSerializer(data=request.data)
        if serializer.is_valid():
            filters = Q()
            
            if serializer.validated_data.get('key'):
                filters &= Q(key__icontains=serializer.validated_data['key'])
            
            if serializer.validated_data.get('config_type'):
                filters &= Q(config_type=serializer.validated_data['config_type'])
            
            if serializer.validated_data.get('service_name'):
                filters &= Q(service_name__icontains=serializer.validated_data['service_name'])
            
            if serializer.validated_data.get('environment'):
                filters &= Q(environment=serializer.validated_data['environment'])
            
            if serializer.validated_data.get('is_sensitive') is not None:
                filters &= Q(is_sensitive=serializer.validated_data['is_sensitive'])
            
            configs = Configuration.objects.filter(filters).exclude(expires_at__lt=timezone.now())
            serializer = ConfigurationListSerializer(configs, many=True)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceHealthSummaryView(APIView):
    """Get health summary for services"""
    
    def get(self, request):
        service_name = request.query_params.get('service_name')
        health_service = HealthCheckService()
        summary = health_service.get_health_summary(service_name)
        
        # Convert to serializer format
        summary_data = []
        for service_name, data in summary.items():
            summary_data.append({
                'service_name': service_name,
                'total_instances': data['total_instances'],
                'healthy_instances': data['healthy_instances'],
                'unhealthy_instances': data['unhealthy_instances'],
                'maintenance_instances': data['maintenance_instances'],
                'overall_status': 'healthy' if data['healthy_instances'] > 0 else 'unhealthy',
                'last_health_check': data['last_health_check'],
                'average_response_time': data['average_response_time']
            })
        
        serializer = ServiceHealthSummarySerializer(summary_data, many=True)
        return Response(serializer.data)


class ServiceDiscoveryStatsView(APIView):
    """Get service discovery statistics"""
    
    def get(self, request):
        stats_service = ServiceDiscoveryStatsService()
        overall_stats = stats_service.get_overall_stats()
        health_stats = stats_service.get_health_stats()
        
        stats = {**overall_stats, **health_stats}
        serializer = ServiceDiscoveryStatsSerializer(stats)
        return Response(serializer.data)


# Service Registration and Heartbeat Views
@api_view(['POST'])
@permission_classes([AllowAny])
def service_registration(request):
    """Register a new service and instance"""
    serializer = ServiceRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        try:
            service_data = {
                'service_name': serializer.validated_data['service_name'],
                'service_type': serializer.validated_data['service_type'],
                'version': serializer.validated_data['version'],
                'base_url': serializer.validated_data['base_url'],
                'health_check_url': serializer.validated_data['health_check_url'],
                'capabilities': serializer.validated_data.get('capabilities', {}),
                'dependencies': serializer.validated_data.get('dependencies', [])
            }
            
            instance_data = {
                'instance_id': serializer.validated_data['instance_id'],
                'host': serializer.validated_data['host'],
                'port': serializer.validated_data['port'],
                'protocol': serializer.validated_data.get('protocol', 'http'),
                'metadata': serializer.validated_data.get('metadata', {})
            }
            
            registry_service = ServiceRegistryService()
            service, instance = registry_service.register_service(service_data, instance_data)
            
            return Response({
                'status': 'success',
                'service_id': str(service.id),
                'instance_id': str(instance.id),
                'message': 'Service registered successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def service_heartbeat(request):
    """Update service heartbeat"""
    serializer = ServiceHeartbeatSerializer(data=request.data)
    if serializer.is_valid():
        try:
            registry_service = ServiceRegistryService()
            instance = registry_service.update_heartbeat(
                service_name=request.data.get('service_name'),
                instance_id=serializer.validated_data['instance_id'],
                status=serializer.validated_data['status'],
                metadata=serializer.validated_data.get('metadata')
            )
            
            if instance:
                # Record metrics if provided
                if serializer.validated_data.get('metrics'):
                    metrics_service = ServiceMetricsService()
                    metrics_service.record_metrics(instance, serializer.validated_data['metrics'])
                
                return Response({
                    'status': 'success',
                    'message': 'Heartbeat updated successfully'
                })
            else:
                return Response({
                    'status': 'error',
                    'message': 'Service instance not found'
                }, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def service_deregistration(request):
    """Deregister a service instance"""
    service_name = request.data.get('service_name')
    instance_id = request.data.get('instance_id')
    
    if not service_name or not instance_id:
        return Response({
            'status': 'error',
            'message': 'service_name and instance_id are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        registry_service = ServiceRegistryService()
        success = registry_service.deregister_service(service_name, instance_id)
        
        if success:
            return Response({
                'status': 'success',
                'message': 'Service deregistered successfully'
            })
        else:
            return Response({
                'status': 'error',
                'message': 'Service instance not found'
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# Configuration Management Views
@api_view(['GET'])
@permission_classes([AllowAny])
def get_configuration(request):
    """Get configuration value"""
    key = request.query_params.get('key')
    service_name = request.query_params.get('service_name')
    environment = request.query_params.get('environment', 'production')
    
    if not key:
        return Response({
            'status': 'error',
            'message': 'key parameter is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        config_service = ConfigurationService()
        value = config_service.get_configuration(key, service_name, environment)
        
        if value is not None:
            return Response({
                'status': 'success',
                'key': key,
                'value': value,
                'service_name': service_name,
                'environment': environment
            })
        else:
            return Response({
                'status': 'error',
                'message': 'Configuration not found'
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_configuration(request):
    """Set configuration value"""
    key = request.data.get('key')
    value = request.data.get('value')
    service_name = request.data.get('service_name')
    environment = request.data.get('environment', 'production')
    description = request.data.get('description', '')
    is_sensitive = request.data.get('is_sensitive', False)
    is_encrypted = request.data.get('is_encrypted', False)
    
    if not key or value is None:
        return Response({
            'status': 'error',
            'message': 'key and value are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        config_service = ConfigurationService()
        config = config_service.set_configuration(
            key=key,
            value=value,
            service_name=service_name,
            environment=environment,
            description=description,
            is_sensitive=is_sensitive,
            is_encrypted=is_encrypted
        )
        
        return Response({
            'status': 'success',
            'config_id': str(config.id),
            'message': 'Configuration set successfully'
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_update_configurations(request):
    """Bulk update configurations"""
    serializer = ConfigurationBulkUpdateSerializer(data=request.data)
    if serializer.is_valid():
        try:
            config_service = ConfigurationService()
            results = config_service.bulk_update_configurations(
                configurations=serializer.validated_data['configurations'],
                environment=serializer.validated_data.get('environment', 'production'),
                service_name=serializer.validated_data.get('service_name'),
                change_reason=serializer.validated_data.get('change_reason', '')
            )
            
            return Response({
                'status': 'success',
                'results': results
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Health Check Management Views
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def perform_health_checks(request):
    """Perform health checks on all services"""
    try:
        health_service = HealthCheckService()
        results = health_service.perform_bulk_health_checks()
        
        return Response({
            'status': 'success',
            'health_checks_performed': len(results),
            'results': [
                {
                    'service_name': check.service_instance.service.service_name,
                    'instance_id': check.service_instance.instance_id,
                    'status': check.status,
                    'response_time_ms': check.response_time_ms
                }
                for check in results
            ]
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def perform_health_check(request):
    """Perform health check on specific service instance"""
    instance_id = request.data.get('instance_id')
    
    if not instance_id:
        return Response({
            'status': 'error',
            'message': 'instance_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        instance = ServiceInstance.objects.get(instance_id=instance_id)
        health_service = HealthCheckService()
        health_check = health_service.perform_health_check(instance)
        
        return Response({
            'status': 'success',
            'health_check_id': str(health_check.id),
            'service_name': instance.service.service_name,
            'instance_id': instance.instance_id,
            'check_status': health_check.status,
            'response_time_ms': health_check.response_time_ms
        })
        
    except ServiceInstance.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Service instance not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# Health Check Endpoint
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint for the service discovery service"""
    return Response({
        'status': 'healthy',
        'service': 'service_discovery',
        'timestamp': timezone.now().isoformat(),
        'endpoints': {
            'services': '/api/service-discovery/services/',
            'instances': '/api/service-discovery/instances/',
            'configurations': '/api/service-discovery/configurations/',
            'health_checks': '/api/service-discovery/health-checks/',
            'registration': '/api/service-discovery/register/',
            'heartbeat': '/api/service-discovery/heartbeat/',
            'stats': '/api/service-discovery/stats/',
            'health': '/api/service-discovery/health/'
        }
    }, status=status.HTTP_200_OK)
