import json
import redis
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .django_middleware import (
    health_check_with_metrics,
    update_inventory_metrics,
    update_circuit_breaker_metrics,
    update_database_metrics
)


@api_view(['GET'])
@permission_classes([AllowAny])
def prometheus_metrics(request):
    """Prometheus metrics endpoint"""
    try:
        # Update dynamic metrics before serving
        update_inventory_metrics()
        update_circuit_breaker_metrics()
        update_database_metrics()
        
        metrics_data = generate_latest()
        return HttpResponse(metrics_data, content_type=CONTENT_TYPE_LATEST)
        
    except Exception as e:
        return HttpResponse(f"Error generating metrics: {str(e)}", status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Enhanced health check endpoint"""
    try:
        health_data = health_check_with_metrics()
        
        if health_data['status'] == 'healthy':
            return Response(health_data, status=status.HTTP_200_OK)
        else:
            return Response(health_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def business_metrics(request):
    """Business metrics endpoint"""
    try:
        # Get business metrics from various sources
        from orders.models import Order
        from payments.models import Payment
        from authentication.models import User
        from inventory.models import InventoryItem
        
        # Calculate business metrics
        today = timezone.now().date()
        
        metrics = {
            'timestamp': timezone.now().isoformat(),
            'orders': {
                'total_today': Order.objects.filter(created_at__date=today).count(),
                'total_pending': Order.objects.filter(status='pending').count(),
                'total_completed': Order.objects.filter(status='completed').count(),
                'revenue_today': float(Order.objects.filter(
                    created_at__date=today,
                    status='completed'
                ).aggregate(total=models.Sum('total_amount'))['total'] or 0)
            },
            'payments': {
                'total_today': Payment.objects.filter(created_at__date=today).count(),
                'successful_today': Payment.objects.filter(
                    created_at__date=today,
                    status='completed'
                ).count(),
                'failed_today': Payment.objects.filter(
                    created_at__date=today,
                    status='failed'
                ).count()
            },
            'users': {
                'total': User.objects.count(),
                'active_today': User.objects.filter(last_login__date=today).count(),
                'registered_today': User.objects.filter(date_joined__date=today).count()
            },
            'inventory': {
                'total_products': InventoryItem.objects.count(),
                'low_stock_items': InventoryItem.objects.filter(
                    quantity_available__lt=10
                ).count(),
                'out_of_stock': InventoryItem.objects.filter(
                    quantity_available=0
                ).count()
            }
        }
        
        return Response(metrics)
        
    except Exception as e:
        return Response({
            'error': 'Failed to retrieve business metrics',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def performance_metrics(request):
    """Performance metrics endpoint"""
    try:
        redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        
        # Get recent performance logs
        perf_logs = redis_client.lrange('performance_logs', 0, 99)
        performance_data = [json.loads(log) for log in perf_logs]
        
        # Calculate aggregated metrics
        if performance_data:
            durations = [log['duration_ms'] for log in performance_data]
            memory_deltas = [log['memory_delta_mb'] for log in performance_data]
            
            metrics = {
                'timestamp': timezone.now().isoformat(),
                'request_count': len(performance_data),
                'average_response_time_ms': sum(durations) / len(durations),
                'max_response_time_ms': max(durations),
                'min_response_time_ms': min(durations),
                'p95_response_time_ms': sorted(durations)[int(len(durations) * 0.95)],
                'average_memory_delta_mb': sum(memory_deltas) / len(memory_deltas),
                'recent_requests': performance_data[:10]  # Last 10 requests
            }
        else:
            metrics = {
                'timestamp': timezone.now().isoformat(),
                'request_count': 0,
                'message': 'No performance data available'
            }
        
        return Response(metrics)
        
    except Exception as e:
        return Response({
            'error': 'Failed to retrieve performance metrics',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tracing_info(request):
    """Distributed tracing information"""
    try:
        # Get tracing configuration and status
        tracing_info = {
            'timestamp': timezone.now().isoformat(),
            'jaeger_endpoint': 'http://localhost:16686',
            'tracing_enabled': True,
            'current_trace_id': getattr(request, 'trace_id', None),
            'instrumentation': {
                'django': True,
                'requests': True,
                'psycopg2': True
            }
        }
        
        # Get recent traces from Redis cache if available
        redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        recent_traces = redis_client.lrange('recent_traces', 0, 9)
        
        if recent_traces:
            tracing_info['recent_traces'] = [
                json.loads(trace) for trace in recent_traces
            ]
        
        return Response(tracing_info)
        
    except Exception as e:
        return Response({
            'error': 'Failed to retrieve tracing information',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@csrf_exempt
def update_metrics(request):
    """Manually trigger metrics update"""
    try:
        update_inventory_metrics()
        update_circuit_breaker_metrics() 
        update_database_metrics()
        
        return Response({
            'message': 'Metrics updated successfully',
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response({
            'error': 'Failed to update metrics',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def circuit_breaker_status(request):
    """Get circuit breaker status for all services"""
    try:
        redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        circuit_breakers = {}
        
        # Get all circuit breaker keys
        keys = redis_client.keys('circuit_breaker:*')
        
        for key in keys:
            service_name = key.decode().split(':')[1]
            state_data = redis_client.get(key)
            
            if state_data:
                circuit_breakers[service_name] = json.loads(state_data)
        
        return Response({
            'timestamp': timezone.now().isoformat(),
            'circuit_breakers': circuit_breakers
        })
        
    except Exception as e:
        return Response({
            'error': 'Failed to retrieve circuit breaker status',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def service_discovery_health(request):
    """Get health status of all registered services"""
    try:
        from service_discovery.services import HealthCheckService
        
        health_service = HealthCheckService()
        health_summary = health_service.get_health_summary()
        
        return Response({
            'timestamp': timezone.now().isoformat(),
            'services_health': health_summary
        })
        
    except Exception as e:
        return Response({
            'error': 'Failed to retrieve service discovery health',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
