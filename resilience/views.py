import json
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from .patterns import (
    resilience_manager,
    CircuitBreakerConfig,
    RetryConfig,
    BulkheadConfig,
    ChaosEngineeringEngine
)


class ResilienceMetricsView(APIView):
    """Get resilience metrics"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all resilience metrics"""
        try:
            metrics = resilience_manager.get_all_metrics()
            
            return Response({
                'timestamp': timezone.now().isoformat(),
                'resilience_metrics': metrics
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to retrieve resilience metrics',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CircuitBreakerManagementView(APIView):
    """Manage circuit breakers"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all circuit breaker states"""
        try:
            circuit_breakers = {}
            for name, cb in resilience_manager.circuit_breakers.items():
                circuit_breakers[name] = cb.get_metrics()
            
            return Response({
                'timestamp': timezone.now().isoformat(),
                'circuit_breakers': circuit_breakers
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to retrieve circuit breaker states',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """Create or configure a circuit breaker"""
        try:
            data = request.data
            name = data.get('name')
            
            if not name:
                return Response({
                    'error': 'Circuit breaker name is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            config = CircuitBreakerConfig(
                failure_threshold=data.get('failure_threshold', 5),
                success_threshold=data.get('success_threshold', 3),
                timeout=data.get('timeout', 60)
            )
            
            circuit_breaker = resilience_manager.get_circuit_breaker(name, config)
            
            return Response({
                'message': f'Circuit breaker {name} configured successfully',
                'metrics': circuit_breaker.get_metrics()
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to configure circuit breaker',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CircuitBreakerDetailView(APIView):
    """Manage individual circuit breaker"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, name):
        """Get specific circuit breaker metrics"""
        try:
            if name not in resilience_manager.circuit_breakers:
                return Response({
                    'error': f'Circuit breaker {name} not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            circuit_breaker = resilience_manager.circuit_breakers[name]
            
            return Response({
                'timestamp': timezone.now().isoformat(),
                'circuit_breaker': circuit_breaker.get_metrics()
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to retrieve circuit breaker metrics',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def patch(self, request, name):
        """Update circuit breaker state"""
        try:
            if name not in resilience_manager.circuit_breakers:
                return Response({
                    'error': f'Circuit breaker {name} not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            action = request.data.get('action')
            circuit_breaker = resilience_manager.circuit_breakers[name]
            
            if action == 'reset':
                circuit_breaker._transition_to_closed()
                message = f'Circuit breaker {name} reset to CLOSED'
            elif action == 'open':
                circuit_breaker._transition_to_open()
                message = f'Circuit breaker {name} manually opened'
            elif action == 'half_open':
                circuit_breaker._transition_to_half_open()
                message = f'Circuit breaker {name} set to HALF_OPEN'
            else:
                return Response({
                    'error': 'Invalid action. Use: reset, open, or half_open'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'message': message,
                'circuit_breaker': circuit_breaker.get_metrics()
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to update circuit breaker',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BulkheadManagementView(APIView):
    """Manage bulkheads"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all bulkhead states"""
        try:
            bulkheads = {}
            for name, bh in resilience_manager.bulkheads.items():
                bulkheads[name] = bh.get_metrics()
            
            return Response({
                'timestamp': timezone.now().isoformat(),
                'bulkheads': bulkheads
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to retrieve bulkhead states',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """Create or configure a bulkhead"""
        try:
            data = request.data
            name = data.get('name')
            
            if not name:
                return Response({
                    'error': 'Bulkhead name is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            config = BulkheadConfig(
                max_concurrent_calls=data.get('max_concurrent_calls', 10),
                max_wait_duration=data.get('max_wait_duration', 30)
            )
            
            bulkhead = resilience_manager.get_bulkhead(name, config)
            
            return Response({
                'message': f'Bulkhead {name} configured successfully',
                'metrics': bulkhead.get_metrics()
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to configure bulkhead',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChaosEngineeringView(APIView):
    """Chaos engineering management"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get chaos experiment status"""
        try:
            chaos_status = resilience_manager.chaos_engine.get_experiment_status()
            
            return Response({
                'timestamp': timezone.now().isoformat(),
                'chaos_engineering': chaos_status
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to retrieve chaos experiment status',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """Start a chaos experiment"""
        try:
            data = request.data
            experiment_type = data.get('type')
            service_name = data.get('service_name')
            duration = data.get('duration', 300)  # 5 minutes default
            
            if not experiment_type or not service_name:
                return Response({
                    'error': 'experiment type and service_name are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            chaos_engine = resilience_manager.chaos_engine
            
            if experiment_type == 'latency':
                latency_ms = data.get('latency_ms', 100)
                probability = data.get('probability', 0.1)
                
                def experiment():
                    # This would be applied to actual service calls
                    pass
                
                experiment_name = f"latency_{service_name}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
                chaos_engine.start_experiment(experiment_name, experiment, duration)
                
                return Response({
                    'message': f'Latency injection experiment started for {service_name}',
                    'experiment_name': experiment_name,
                    'duration': duration,
                    'parameters': {
                        'latency_ms': latency_ms,
                        'probability': probability
                    }
                })
            
            elif experiment_type == 'failure':
                failure_rate = data.get('failure_rate', 0.1)
                
                def experiment():
                    # This would be applied to actual service calls
                    pass
                
                experiment_name = f"failure_{service_name}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
                chaos_engine.start_experiment(experiment_name, experiment, duration)
                
                return Response({
                    'message': f'Failure injection experiment started for {service_name}',
                    'experiment_name': experiment_name,
                    'duration': duration,
                    'parameters': {
                        'failure_rate': failure_rate
                    }
                })
            
            elif experiment_type == 'resource_exhaustion':
                probability = data.get('probability', 0.05)
                
                def experiment():
                    # This would be applied to actual service calls
                    pass
                
                experiment_name = f"resource_{service_name}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
                chaos_engine.start_experiment(experiment_name, experiment, duration)
                
                return Response({
                    'message': f'Resource exhaustion experiment started for {service_name}',
                    'experiment_name': experiment_name,
                    'duration': duration,
                    'parameters': {
                        'probability': probability
                    }
                })
            
            else:
                return Response({
                    'error': 'Invalid experiment type. Use: latency, failure, or resource_exhaustion'
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'error': 'Failed to start chaos experiment',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_all_resilience(request):
    """Reset all resilience components"""
    try:
        resilience_manager.reset_all()
        
        return Response({
            'message': 'All resilience components reset successfully',
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response({
            'error': 'Failed to reset resilience components',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def resilience_health_check(request):
    """Health check for resilience components"""
    try:
        # Check if any circuit breakers are open
        open_circuit_breakers = [
            name for name, cb in resilience_manager.circuit_breakers.items()
            if cb.state.value == 'open'
        ]
        
        # Check if any bulkheads are at capacity
        overwhelmed_bulkheads = [
            name for name, bh in resilience_manager.bulkheads.items()
            if bh.semaphore._value == 0
        ]
        
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'circuit_breakers': {
                'total': len(resilience_manager.circuit_breakers),
                'open': len(open_circuit_breakers),
                'open_breakers': open_circuit_breakers
            },
            'bulkheads': {
                'total': len(resilience_manager.bulkheads),
                'overwhelmed': len(overwhelmed_bulkheads),
                'overwhelmed_bulkheads': overwhelmed_bulkheads
            },
            'chaos_experiments': {
                'active': len(resilience_manager.chaos_engine.active_experiments)
            }
        }
        
        # Determine overall health
        if open_circuit_breakers or overwhelmed_bulkheads:
            health_status['status'] = 'degraded'
            
            if len(open_circuit_breakers) > len(resilience_manager.circuit_breakers) * 0.5:
                health_status['status'] = 'unhealthy'
        
        status_code = status.HTTP_200_OK
        if health_status['status'] == 'degraded':
            status_code = status.HTTP_206_PARTIAL_CONTENT
        elif health_status['status'] == 'unhealthy':
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        return Response(health_status, status=status_code)
        
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def resilience_dashboard_data(request):
    """Get data for resilience dashboard"""
    try:
        dashboard_data = {
            'timestamp': timezone.now().isoformat(),
            'summary': {
                'total_circuit_breakers': len(resilience_manager.circuit_breakers),
                'open_circuit_breakers': sum(
                    1 for cb in resilience_manager.circuit_breakers.values()
                    if cb.state.value == 'open'
                ),
                'total_bulkheads': len(resilience_manager.bulkheads),
                'active_chaos_experiments': len(resilience_manager.chaos_engine.active_experiments)
            },
            'circuit_breakers': [
                cb.get_metrics() for cb in resilience_manager.circuit_breakers.values()
            ],
            'bulkheads': [
                bh.get_metrics() for bh in resilience_manager.bulkheads.values()
            ],
            'chaos_experiments': resilience_manager.chaos_engine.get_experiment_status()
        }
        
        return Response(dashboard_data)
        
    except Exception as e:
        return Response({
            'error': 'Failed to retrieve dashboard data',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
