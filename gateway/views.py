import graphene
import logging
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from . import resolvers
from .schema import schema
from .middleware import (
    ServiceDiscoveryClient, 
    rate_limit, 
    circuit_breaker,
    CircuitBreakerOpenException,
    ServiceUnavailableException,
    RetryMiddleware
)

logger = logging.getLogger(__name__)

# Initialize components
service_client = ServiceDiscoveryClient()
retry_middleware = RetryMiddleware()


class GraphQLView(View):
    """GraphQL endpoint for the API Gateway"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        """Handle GraphQL queries"""
        try:
            data = request.POST.get('query') or request.body.decode('utf-8')
            if isinstance(data, str):
                # Parse the query
                result = schema.execute(data)
                if result.errors:
                    return JsonResponse({
                        'errors': [str(error) for error in result.errors]
                    }, status=400)
                return JsonResponse({'data': result.data})
            else:
                return JsonResponse({'error': 'Invalid query'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def get(self, request):
        """Handle GraphQL introspection queries"""
        return JsonResponse({
            'message': 'GraphQL Gateway is running. Use POST for queries.',
            'endpoint': '/api/gateway/graphql/',
            'timestamp': timezone.now().isoformat()
        })


class ServiceProxyView(APIView):
    """Proxy view for service calls with enhanced features"""
    
    @rate_limit(requests_per_minute=100)
    def post(self, request, service_name, path=''):
        """Proxy POST requests to services"""
        return self._proxy_request(request, service_name, path, 'POST')
    
    @rate_limit(requests_per_minute=200)
    def get(self, request, service_name, path=''):
        """Proxy GET requests to services"""
        return self._proxy_request(request, service_name, path, 'GET')
    
    @rate_limit(requests_per_minute=50)
    def put(self, request, service_name, path=''):
        """Proxy PUT requests to services"""
        return self._proxy_request(request, service_name, path, 'PUT')
    
    @rate_limit(requests_per_minute=50)
    def patch(self, request, service_name, path=''):
        """Proxy PATCH requests to services"""
        return self._proxy_request(request, service_name, path, 'PATCH')
    
    @rate_limit(requests_per_minute=30)
    def delete(self, request, service_name, path=''):
        """Proxy DELETE requests to services"""
        return self._proxy_request(request, service_name, path, 'DELETE')
    
    def _proxy_request(self, request, service_name, path, method):
        """Proxy request to service with circuit breaker and retry"""
        try:
            # Prepare headers
            headers = self._prepare_headers(request)
            
            # Prepare data
            data = None
            if method in ['POST', 'PUT', 'PATCH']:
                if request.content_type == 'application/json':
                    data = json.loads(request.body) if request.body else None
                else:
                    data = dict(request.POST)
            
            # Add query parameters
            query_params = dict(request.GET)
            if query_params:
                path += '?' + '&'.join([f"{k}={v}" for k, v in query_params.items()])
            
            # Make service call with retry
            def make_call():
                return service_client.call_service(
                    service_name=service_name,
                    path=f'/api/{path}',
                    method=method,
                    data=data,
                    headers=headers,
                    timeout=30
                )
            
            response = retry_middleware.retry_call(make_call)
            
            # Return response
            return Response(
                data=response.json() if response.content else {},
                status=response.status_code,
                headers={
                    'X-Gateway-Service': service_name,
                    'X-Gateway-Method': method,
                    'X-Response-Time': str(response.elapsed.total_seconds())
                }
            )
            
        except CircuitBreakerOpenException:
            return Response({
                'error': 'Service Unavailable',
                'message': f'Service {service_name} is currently unavailable',
                'code': 'CIRCUIT_BREAKER_OPEN'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        except ServiceUnavailableException:
            return Response({
                'error': 'Service Unavailable',
                'message': f'No healthy instances available for {service_name}',
                'code': 'NO_HEALTHY_INSTANCES'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        except Exception as e:
            logger.error(f"Gateway proxy error for {service_name}: {e}")
            return Response({
                'error': 'Gateway Error',
                'message': 'An error occurred while processing your request',
                'code': 'GATEWAY_ERROR'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _prepare_headers(self, request):
        """Prepare headers for service call"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'API-Gateway/1.0'
        }
        
        # Forward authentication headers
        if 'HTTP_AUTHORIZATION' in request.META:
            headers['Authorization'] = request.META['HTTP_AUTHORIZATION']
        
        # Forward trace headers
        for header_name in ['X-Trace-ID', 'X-Request-ID', 'X-Correlation-ID']:
            if f'HTTP_{header_name.upper().replace("-", "_")}' in request.META:
                headers[header_name] = request.META[f'HTTP_{header_name.upper().replace("-", "_")}']
        
        return headers


class GatewayStatsView(APIView):
    """Gateway statistics and monitoring"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get gateway statistics"""
        try:
            from django.core.cache import cache
            import redis
            
            redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            
            # Get circuit breaker states
            circuit_breaker_keys = redis_client.keys('circuit_breaker:*')
            circuit_breakers = {}
            
            for key in circuit_breaker_keys:
                service_name = key.decode().split(':')[1]
                state_data = redis_client.get(key)
                if state_data:
                    circuit_breakers[service_name] = json.loads(state_data)
            
            # Get rate limit stats (sample)
            rate_limit_stats = {
                'total_requests_last_minute': 0,
                'blocked_requests_last_minute': 0
            }
            
            # Get service health from service discovery
            from service_discovery.services import ServiceDiscoveryStatsService, HealthCheckService
            
            stats_service = ServiceDiscoveryStatsService()
            health_service = HealthCheckService()
            
            overall_stats = stats_service.get_overall_stats()
            health_summary = health_service.get_health_summary()
            
            return Response({
                'gateway_stats': {
                    'timestamp': timezone.now().isoformat(),
                    'circuit_breakers': circuit_breakers,
                    'rate_limiting': rate_limit_stats,
                    'services': overall_stats,
                    'health_summary': health_summary
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting gateway stats: {e}")
            return Response({
                'error': 'Stats Error',
                'message': 'Could not retrieve gateway statistics'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoadBalancerConfigView(APIView):
    """Configure load balancer settings"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get load balancer configuration"""
        return Response({
            'algorithms': ['round_robin', 'weighted_round_robin', 'least_connections', 'random'],
            'current_algorithm': 'round_robin',
            'health_check_interval': 30,
            'circuit_breaker_settings': {
                'failure_threshold': 5,
                'recovery_timeout': 60
            }
        })
    
    def post(self, request):
        """Update load balancer configuration"""
        algorithm = request.data.get('algorithm', 'round_robin')
        
        # Validate algorithm
        valid_algorithms = ['round_robin', 'weighted_round_robin', 'least_connections', 'random']
        if algorithm not in valid_algorithms:
            return Response({
                'error': 'Invalid algorithm',
                'valid_options': valid_algorithms
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update configuration (in a real system, this would persist to database)
        cache.set('load_balancer_algorithm', algorithm, 3600)
        
        return Response({
            'message': 'Load balancer configuration updated',
            'algorithm': algorithm
        })


@api_view(['GET'])
@permission_classes([AllowAny])
@rate_limit(requests_per_minute=300)
def health_check(request):
    """Health check endpoint for the API Gateway"""
    try:
        # Check service discovery health
        from service_discovery.views import health_check as sd_health
        
        # Basic health check
        gateway_health = {
            'status': 'healthy',
            'service': 'gateway',
            'timestamp': timezone.now().isoformat(),
            'endpoints': {
                'graphql': '/api/gateway/graphql/',
                'proxy': '/api/gateway/proxy/<service>/<path>/',
                'stats': '/api/gateway/stats/',
                'config': '/api/gateway/config/',
                'health': '/api/gateway/health/'
            }
        }
        
        # Check Redis connectivity
        try:
            import redis
            redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            redis_client.ping()
            gateway_health['redis'] = 'healthy'
        except Exception as e:
            gateway_health['redis'] = f'unhealthy: {str(e)}'
            gateway_health['status'] = 'degraded'
        
        # Check service discovery
        try:
            from service_discovery.services import ServiceRegistryService
            registry_service = ServiceRegistryService()
            services = registry_service.get_all_services(status='active')
            gateway_health['registered_services'] = services.count()
        except Exception as e:
            gateway_health['service_discovery'] = f'error: {str(e)}'
            gateway_health['status'] = 'degraded'
        
        return Response(gateway_health, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Gateway health check error: {e}")
        return Response({
            'status': 'unhealthy',
            'service': 'gateway',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
