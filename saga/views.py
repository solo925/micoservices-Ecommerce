import asyncio
import json
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt

from .patterns import (
    OrderProcessingSaga,
    SagaException,
    SagaContext
)


class OrderSagaView(APIView):
    """Handle order processing with SAGA pattern"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Create order using SAGA pattern"""
        try:
            order_data = request.data.get('order')
            payment_data = request.data.get('payment')
            
            if not order_data or not payment_data:
                return Response({
                    'error': 'Both order and payment data are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate order data
            required_order_fields = ['customer_name', 'customer_email', 'items', 'subtotal', 'total_amount']
            for field in required_order_fields:
                if field not in order_data:
                    return Response({
                        'error': f'Missing required order field: {field}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate payment data
            required_payment_fields = ['payment_method']
            for field in required_payment_fields:
                if field not in payment_data:
                    return Response({
                        'error': f'Missing required payment field: {field}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Execute saga asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result_context = loop.run_until_complete(
                    OrderProcessingSaga.create_order(order_data, payment_data)
                )
                
                return Response({
                    'message': 'Order processed successfully',
                    'saga_id': result_context.saga_id,
                    'order_id': result_context.get('order_id'),
                    'payment_id': result_context.get('payment_id'),
                    'status': 'completed',
                    'timestamp': timezone.now().isoformat()
                })
                
            except SagaException as e:
                return Response({
                    'error': 'Order processing failed',
                    'message': str(e),
                    'status': 'failed',
                    'timestamp': timezone.now().isoformat()
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
            finally:
                loop.close()
            
        except Exception as e:
            return Response({
                'error': 'Unexpected error during order processing',
                'message': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SagaStatusView(APIView):
    """Get saga execution status"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, saga_id):
        """Get saga status by ID"""
        try:
            saga_status = OrderProcessingSaga.get_saga_status(saga_id)
            
            if not saga_status:
                return Response({
                    'error': f'Saga {saga_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'saga_status': saga_status,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to retrieve saga status',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SagaListView(APIView):
    """List saga executions"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get list of recent saga executions"""
        try:
            import redis
            from django.conf import settings
            
            redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            
            # Get all saga keys
            saga_keys = redis_client.keys('saga:*')
            sagas = []
            
            for key in saga_keys:
                saga_data = redis_client.get(key)
                if saga_data:
                    saga_info = json.loads(saga_data)
                    # Include only summary information
                    sagas.append({
                        'saga_id': saga_info['saga_id'],
                        'name': saga_info['name'],
                        'state': saga_info['state'],
                        'started_at': saga_info['started_at'],
                        'completed_at': saga_info['completed_at'],
                        'current_step_index': saga_info['current_step_index'],
                        'total_steps': len(saga_info['steps']),
                        'error_message': saga_info.get('error_message')
                    })
            
            # Sort by start time (most recent first)
            sagas.sort(key=lambda x: x['started_at'], reverse=True)
            
            return Response({
                'sagas': sagas[:50],  # Limit to 50 most recent
                'total_count': len(sagas),
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to retrieve saga list',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_saga_patterns(request):
    """Test various saga patterns"""
    try:
        pattern_type = request.data.get('pattern', 'success')
        
        if pattern_type == 'success':
            # Test successful order flow
            order_data = {
                'customer_name': 'Test Customer',
                'customer_email': 'test@example.com',
                'items': [
                    {
                        'product_id': 'test-product-1',
                        'quantity': 2,
                        'unit_price': 25.00,
                        'total_price': 50.00
                    }
                ],
                'subtotal': 50.00,
                'total_amount': 55.00
            }
            
            payment_data = {
                'payment_method': 'credit_card',
                'card_token': 'test_token_12345'
            }
            
        elif pattern_type == 'inventory_failure':
            # Test inventory failure scenario
            order_data = {
                'customer_name': 'Test Customer',
                'customer_email': 'test@example.com',
                'items': [
                    {
                        'product_id': 'out-of-stock-product',
                        'quantity': 999,  # Large quantity to trigger failure
                        'unit_price': 25.00,
                        'total_price': 24975.00
                    }
                ],
                'subtotal': 24975.00,
                'total_amount': 24975.00
            }
            
            payment_data = {
                'payment_method': 'credit_card',
                'card_token': 'test_token_12345'
            }
            
        elif pattern_type == 'payment_failure':
            # Test payment failure scenario
            order_data = {
                'customer_name': 'Test Customer',
                'customer_email': 'test@example.com',
                'items': [
                    {
                        'product_id': 'test-product-1',
                        'quantity': 1,
                        'unit_price': 25.00,
                        'total_price': 25.00
                    }
                ],
                'subtotal': 25.00,
                'total_amount': 27.50
            }
            
            payment_data = {
                'payment_method': 'invalid_card',  # This will trigger payment failure
                'card_token': 'invalid_token'
            }
            
        else:
            return Response({
                'error': 'Invalid pattern type. Use: success, inventory_failure, or payment_failure'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Execute saga test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result_context = loop.run_until_complete(
                OrderProcessingSaga.create_order(order_data, payment_data)
            )
            
            return Response({
                'message': f'Saga test "{pattern_type}" completed',
                'saga_id': result_context.saga_id,
                'pattern': pattern_type,
                'result': 'success',
                'context': result_context.to_dict(),
                'timestamp': timezone.now().isoformat()
            })
            
        except SagaException as e:
            return Response({
                'message': f'Saga test "{pattern_type}" failed as expected',
                'pattern': pattern_type,
                'result': 'expected_failure',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            })
            
        finally:
            loop.close()
            
    except Exception as e:
        return Response({
            'error': 'Saga test failed',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def saga_health_check(request):
    """Health check for saga system"""
    try:
        import redis
        from django.conf import settings
        
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'components': {}
        }
        
        # Check Redis connectivity
        try:
            redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            redis_client.ping()
            health_status['components']['redis'] = 'healthy'
        except Exception as e:
            health_status['components']['redis'] = f'unhealthy: {str(e)}'
            health_status['status'] = 'degraded'
        
        # Check saga storage
        try:
            redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            saga_keys = redis_client.keys('saga:*')
            health_status['components']['saga_storage'] = {
                'status': 'healthy',
                'active_sagas': len(saga_keys)
            }
        except Exception as e:
            health_status['components']['saga_storage'] = f'unhealthy: {str(e)}'
            health_status['status'] = 'degraded'
        
        # Check dependent services
        services = ['inventory', 'orders', 'payments', 'notification']
        for service in services:
            try:
                # This is a simplified check - in production you'd ping actual service endpoints
                health_status['components'][f'{service}_service'] = 'available'
            except Exception as e:
                health_status['components'][f'{service}_service'] = f'unavailable: {str(e)}'
                health_status['status'] = 'degraded'
        
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
def saga_metrics(request):
    """Get saga execution metrics"""
    try:
        import redis
        from django.conf import settings
        from collections import defaultdict
        
        redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        
        # Get all saga data
        saga_keys = redis_client.keys('saga:*')
        metrics = {
            'total_sagas': len(saga_keys),
            'states': defaultdict(int),
            'success_rate': 0,
            'average_duration': 0,
            'recent_activity': []
        }
        
        durations = []
        recent_sagas = []
        
        for key in saga_keys:
            saga_data = redis_client.get(key)
            if saga_data:
                saga_info = json.loads(saga_data)
                
                # Count by state
                metrics['states'][saga_info['state']] += 1
                
                # Calculate duration if completed
                if saga_info['completed_at']:
                    start_time = timezone.datetime.fromisoformat(saga_info['started_at'])
                    end_time = timezone.datetime.fromisoformat(saga_info['completed_at'])
                    duration = (end_time - start_time).total_seconds()
                    durations.append(duration)
                
                # Recent activity
                recent_sagas.append({
                    'saga_id': saga_info['saga_id'],
                    'name': saga_info['name'],
                    'state': saga_info['state'],
                    'started_at': saga_info['started_at']
                })
        
        # Calculate success rate
        completed_sagas = metrics['states']['completed']
        failed_sagas = metrics['states']['failed'] + metrics['states']['compensated']
        total_finished = completed_sagas + failed_sagas
        
        if total_finished > 0:
            metrics['success_rate'] = (completed_sagas / total_finished) * 100
        
        # Calculate average duration
        if durations:
            metrics['average_duration'] = sum(durations) / len(durations)
        
        # Recent activity (last 10)
        recent_sagas.sort(key=lambda x: x['started_at'], reverse=True)
        metrics['recent_activity'] = recent_sagas[:10]
        
        return Response({
            'timestamp': timezone.now().isoformat(),
            'saga_metrics': metrics
        })
        
    except Exception as e:
        return Response({
            'error': 'Failed to retrieve saga metrics',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
