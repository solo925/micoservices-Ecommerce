from rest_framework import generics, status, permissions, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, F
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
from datetime import datetime, timedelta
import uuid

from .models import (
    NotificationTemplate, NotificationChannel, Notification, NotificationDelivery,
    NotificationPreference, NotificationLog, NotificationBatch
)
from .serializers import (
    NotificationTemplateSerializer, NotificationTemplateCreateSerializer,
    NotificationChannelSerializer, NotificationChannelCreateSerializer,
    NotificationSerializer, NotificationCreateSerializer, NotificationUpdateSerializer,
    NotificationStatusUpdateSerializer, NotificationDeliverySerializer,
    NotificationPreferenceSerializer, NotificationPreferenceUpdateSerializer,
    NotificationLogSerializer, NotificationBatchSerializer, NotificationBatchCreateSerializer,
    NotificationBatchStatusUpdateSerializer, OrderNotificationSerializer,
    PaymentNotificationSerializer, LowStockAlertSerializer, PromotionNotificationSerializer,
    BulkNotificationSerializer, NotificationStatsSerializer, NotificationSearchSerializer,
    NotificationRetrySerializer, NotificationTemplateTestSerializer,
    NotificationChannelTestSerializer, NotificationPreferenceBulkUpdateSerializer
)
from .services import (
    NotificationService, NotificationDeliveryService, NotificationBatchService,
    NotificationStatsService, NotificationPreferenceService
)


# Template Views
class NotificationTemplateListCreateView(generics.ListCreateAPIView):
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['template_type', 'is_active']
    search_fields = ['name', 'subject', 'content']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['-created_at']


class NotificationTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer


class NotificationTemplateCreateView(generics.CreateAPIView):
    serializer_class = NotificationTemplateCreateSerializer


# Channel Views
class NotificationChannelListCreateView(generics.ListCreateAPIView):
    queryset = NotificationChannel.objects.all()
    serializer_class = NotificationChannelSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['channel_type', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class NotificationChannelDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = NotificationChannel.objects.all()
    serializer_class = NotificationChannelSerializer


class NotificationChannelCreateView(generics.CreateAPIView):
    serializer_class = NotificationChannelCreateSerializer


# Notification Views
class NotificationListCreateView(generics.ListCreateAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'channel', 'template', 'priority', 'is_sent', 'delivery_status']
    search_fields = ['recipient_email', 'recipient_phone', 'subject', 'content']
    ordering_fields = ['created_at', 'scheduled_at', 'sent_at', 'priority']
    ordering = ['-created_at']


class NotificationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer


class NotificationCreateView(generics.CreateAPIView):
    serializer_class = NotificationCreateSerializer


class NotificationUpdateView(generics.UpdateAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationUpdateSerializer


class NotificationStatusUpdateView(generics.UpdateAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationStatusUpdateSerializer


# Delivery Views
class NotificationDeliveryListView(generics.ListAPIView):
    queryset = NotificationDelivery.objects.all()
    serializer_class = NotificationDeliverySerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'notification', 'attempt_number']
    ordering_fields = ['created_at', 'sent_at', 'delivered_at']
    ordering = ['-created_at']


class NotificationDeliveryDetailView(generics.RetrieveAPIView):
    queryset = NotificationDelivery.objects.all()
    serializer_class = NotificationDeliverySerializer


# Preference Views
class NotificationPreferenceListCreateView(generics.ListCreateAPIView):
    queryset = NotificationPreference.objects.all()
    serializer_class = NotificationPreferenceSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['email_enabled', 'sms_enabled', 'push_enabled', 'digest_frequency']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']


class NotificationPreferenceDetailView(generics.RetrieveUpdateAPIView):
    queryset = NotificationPreference.objects.all()
    serializer_class = NotificationPreferenceSerializer


class NotificationPreferenceUpdateView(generics.UpdateAPIView):
    queryset = NotificationPreference.objects.all()
    serializer_class = NotificationPreferenceUpdateSerializer


# Batch Views
class NotificationBatchListCreateView(generics.ListCreateAPIView):
    queryset = NotificationBatch.objects.all()
    serializer_class = NotificationBatchSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'template', 'channel']
    search_fields = ['name']
    ordering_fields = ['created_at', 'scheduled_at', 'started_at', 'completed_at']
    ordering = ['-created_at']


class NotificationBatchDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = NotificationBatch.objects.all()
    serializer_class = NotificationBatchSerializer


class NotificationBatchCreateView(generics.CreateAPIView):
    serializer_class = NotificationBatchCreateSerializer


class NotificationBatchStatusUpdateView(generics.UpdateAPIView):
    queryset = NotificationBatch.objects.all()
    serializer_class = NotificationBatchStatusUpdateSerializer


# Log Views
class NotificationLogListView(generics.ListAPIView):
    queryset = NotificationLog.objects.all()
    serializer_class = NotificationLogSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['level', 'notification', 'channel', 'user_id']
    search_fields = ['message']
    ordering_fields = ['created_at', 'level']
    ordering = ['-created_at']


class NotificationLogDetailView(generics.RetrieveAPIView):
    queryset = NotificationLog.objects.all()
    serializer_class = NotificationLogSerializer


# Specialized Notification Views
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_order_notification(request):
    """Send order-related notification"""
    serializer = OrderNotificationSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        
        # Create notification context
        context_data = {
            'customer_name': data['customer_name'],
            'order_number': data['order_number'],
            'total_amount': str(data['total_amount']),
            'status': data['status'],
            'tracking_number': data.get('tracking_number', ''),
            'estimated_delivery': data.get('estimated_delivery', ''),
        }
        
        # Determine notification type based on status
        notification_type = 'order_confirmation'
        if data['status'] in ['shipped', 'delivered']:
            notification_type = f"order_{data['status']}"
        
        try:
            notification = NotificationService.create_notification(
                notification_type=notification_type,
                recipient_email=data['customer_email'],
                subject=f"Order {data['order_number']} - {data['status'].title()}",
                content=f"Your order {data['order_number']} has been {data['status']}.",
                context_data=context_data,
                metadata={'order_id': str(data['order_id'])}
            )
            
            if notification:
                # Send immediately
                success, error = NotificationDeliveryService.send_notification(notification)
                return Response({
                    'success': success,
                    'notification_id': str(notification.id),
                    'error': error if not success else None
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': 'Notification blocked by user preferences or rate limiting'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_payment_notification(request):
    """Send payment-related notification"""
    serializer = PaymentNotificationSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        
        context_data = {
            'amount': str(data['amount']),
            'currency': data['currency'],
            'status': data['status'],
            'transaction_id': data['transaction_id'],
        }
        
        notification_type = f"payment_{data['status']}"
        
        try:
            notification = NotificationService.create_notification(
                notification_type=notification_type,
                recipient_email=data['customer_email'],
                subject=f"Payment {data['status'].title()} - {data['transaction_id']}",
                content=f"Your payment of {data['amount']} {data['currency']} has been {data['status']}.",
                context_data=context_data,
                metadata={'payment_id': str(data['payment_id']), 'order_id': str(data['order_id'])}
            )
            
            if notification:
                success, error = NotificationDeliveryService.send_notification(notification)
                return Response({
                    'success': success,
                    'notification_id': str(notification.id),
                    'error': error if not success else None
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': 'Notification blocked by user preferences or rate limiting'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_low_stock_alert(request):
    """Send low stock alert notification"""
    serializer = LowStockAlertSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        
        context_data = {
            'product_name': data['product_name'],
            'current_stock': data['current_stock'],
            'threshold': data['threshold'],
        }
        
        try:
            notification = NotificationService.create_notification(
                notification_type='low_stock_alert',
                subject=f"Low Stock Alert - {data['product_name']}",
                content=f"Product {data['product_name']} is running low on stock. Current: {data['current_stock']}, Threshold: {data['threshold']}",
                context_data=context_data,
                priority='high',
                metadata={'product_id': str(data['product_id'])}
            )
            
            if notification:
                success, error = NotificationDeliveryService.send_notification(notification)
                return Response({
                    'success': success,
                    'notification_id': str(notification.id),
                    'error': error if not success else None
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': 'Notification blocked by rate limiting'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_promotion_notification(request):
    """Send promotion notification"""
    serializer = PromotionNotificationSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        
        context_data = {
            'title': data['title'],
            'description': data['description'],
            'valid_until': data['valid_until'].strftime('%Y-%m-%d'),
            'code': data.get('code', ''),
        }
        
        if data.get('discount_percentage'):
            context_data['discount_percentage'] = data['discount_percentage']
        if data.get('discount_amount'):
            context_data['discount_amount'] = str(data['discount_amount'])
        
        try:
            notification = NotificationService.create_notification(
                notification_type='promotion',
                subject=f"Special Promotion: {data['title']}",
                content=f"New promotion: {data['description']}",
                context_data=context_data,
                metadata={'promotion_id': str(data['promotion_id'])}
            )
            
            if notification:
                success, error = NotificationDeliveryService.send_notification(notification)
                return Response({
                    'success': success,
                    'notification_id': str(notification.id),
                    'error': error if not success else None
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': 'Notification blocked by user preferences or rate limiting'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_bulk_notification(request):
    """Send bulk notifications"""
    serializer = BulkNotificationSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        
        try:
            batch = NotificationBatchService.create_batch_notification({
                'name': f"Bulk notification - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                'template_id': data['template_id'],
                'channel_id': data['channel_id'],
                'recipients': data['recipients'],
                'scheduled_at': data.get('scheduled_at'),
                'batch_size': data.get('batch_size', 100),
                'delay_between_batches': data.get('delay_between_batches', 60)
            })
            
            return Response({
                'success': True,
                'batch_id': str(batch.id),
                'total_recipients': batch.total_recipients
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def process_batch_notification(request, batch_id):
    """Process a batch notification"""
    try:
        batch = NotificationBatchService.process_batch(batch_id)
        return Response({
            'success': True,
            'batch_id': str(batch.id),
            'status': batch.status,
            'sent_count': batch.sent_count,
            'failed_count': batch.failed_count
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def retry_notification(request):
    """Retry a failed notification"""
    serializer = NotificationRetrySerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        
        try:
            notification = Notification.objects.get(id=data['notification_id'])
            
            if notification.is_sent and not data.get('force_retry'):
                return Response({
                    'success': False,
                    'error': 'Notification already sent'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not notification.can_retry:
                return Response({
                    'success': False,
                    'error': 'Notification cannot be retried'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            success, error = NotificationDeliveryService.send_notification(notification)
            
            return Response({
                'success': success,
                'notification_id': str(notification.id),
                'error': error if not success else None
            }, status=status.HTTP_200_OK)
            
        except Notification.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Notification not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def test_template(request):
    """Test a notification template"""
    serializer = NotificationTemplateTestSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        
        try:
            template = NotificationTemplate.objects.get(id=data['template_id'])
            
            # Render template with test data
            subject = NotificationService.render_template(template.subject, data['test_data'])
            content = NotificationService.render_template(template.content, data['test_data'])
            html_content = NotificationService.render_template(template.html_content, data['test_data'])
            
            # Send test notification if channel and recipient provided
            if data.get('channel_id') and (data.get('recipient_email') or data.get('recipient_phone')):
                notification = NotificationService.create_notification(
                    notification_type='custom',
                    recipient_email=data.get('recipient_email'),
                    recipient_phone=data.get('recipient_phone'),
                    template_id=data['template_id'],
                    channel_id=data['channel_id'],
                    subject=subject,
                    content=content,
                    html_content=html_content,
                    context_data=data['test_data'],
                    metadata={'test': True}
                )
                
                if notification:
                    success, error = NotificationDeliveryService.send_notification(notification)
                    return Response({
                        'success': True,
                        'rendered_subject': subject,
                        'rendered_content': content,
                        'rendered_html_content': html_content,
                        'test_sent': success,
                        'test_error': error if not success else None
                    }, status=status.HTTP_200_OK)
            
            return Response({
                'success': True,
                'rendered_subject': subject,
                'rendered_content': content,
                'rendered_html_content': html_content
            }, status=status.HTTP_200_OK)
            
        except NotificationTemplate.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Template not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def test_channel(request):
    """Test a notification channel"""
    serializer = NotificationChannelTestSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        
        try:
            channel = NotificationChannel.objects.get(id=data['channel_id'])
            
            # Create test notification
            notification = NotificationService.create_notification(
                notification_type='custom',
                recipient_email=data.get('test_email'),
                recipient_phone=data.get('test_phone'),
                channel_id=data['channel_id'],
                subject='Test Notification',
                content=data['test_message'],
                metadata={'test': True}
            )
            
            if notification:
                success, error = NotificationDeliveryService.send_notification(notification)
                return Response({
                    'success': success,
                    'channel_id': str(channel.id),
                    'channel_name': channel.name,
                    'error': error if not success else None
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to create test notification'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except NotificationChannel.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Channel not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def notification_stats(request):
    """Get notification statistics"""
    try:
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if date_from:
            date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        if date_to:
            date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        
        stats = NotificationStatsService.get_notification_stats(date_from, date_to)
        
        serializer = NotificationStatsSerializer(data=stats)
        if serializer.is_valid():
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def channel_stats(request, channel_id):
    """Get statistics for a specific channel"""
    try:
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if date_from:
            date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        if date_to:
            date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        
        stats = NotificationStatsService.get_channel_stats(channel_id, date_from, date_to)
        
        return Response(stats, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search_notifications(request):
    """Search notifications with filters"""
    try:
        serializer = NotificationSearchSerializer(data=request.query_params)
        if serializer.is_valid():
            filters = serializer.validated_data
            
            queryset = Notification.objects.all()
            
            if filters.get('notification_type'):
                queryset = queryset.filter(notification_type=filters['notification_type'])
            
            if filters.get('recipient_email'):
                queryset = queryset.filter(recipient_email__icontains=filters['recipient_email'])
            
            if filters.get('recipient_user_id'):
                queryset = queryset.filter(recipient_user_id=filters['recipient_user_id'])
            
            if filters.get('status'):
                queryset = queryset.filter(delivery_status=filters['status'])
            
            if filters.get('channel'):
                queryset = queryset.filter(channel_id=filters['channel'])
            
            if filters.get('template'):
                queryset = queryset.filter(template_id=filters['template'])
            
            if filters.get('priority'):
                queryset = queryset.filter(priority=filters['priority'])
            
            if filters.get('date_from'):
                queryset = queryset.filter(created_at__gte=filters['date_from'])
            
            if filters.get('date_to'):
                queryset = queryset.filter(created_at__lte=filters['date_to'])
            
            # Pagination
            page = request.query_params.get('page', 1)
            page_size = request.query_params.get('page_size', 20)
            
            paginator = Paginator(queryset, page_size)
            notifications = paginator.get_page(page)
            
            serializer = NotificationSerializer(notifications, many=True)
            
            return Response({
                'results': serializer.data,
                'count': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': int(page)
            }, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT'])
@permission_classes([permissions.IsAuthenticated])
def user_preferences(request, user_id):
    """Get or update user notification preferences"""
    if request.method == 'GET':
        try:
            preferences = NotificationPreferenceService.get_or_create_preferences(user_id)
            serializer = NotificationPreferenceSerializer(preferences)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'PUT':
        try:
            serializer = NotificationPreferenceUpdateSerializer(data=request.data)
            if serializer.is_valid():
                preferences = NotificationPreferenceService.update_preferences(
                    user_id, serializer.validated_data
                )
                response_serializer = NotificationPreferenceSerializer(preferences)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def bulk_update_preferences(request):
    """Bulk update notification preferences"""
    serializer = NotificationPreferenceBulkUpdateSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        
        try:
            updated_count = NotificationPreferenceService.bulk_update_preferences(
                data['user_ids'], data['preferences']
            )
            
            return Response({
                'success': True,
                'updated_count': updated_count
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'service': 'notification',
        'timestamp': timezone.now().isoformat()
    }, status=status.HTTP_200_OK)
