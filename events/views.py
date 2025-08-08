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

from .models import Event, EventSubscription, EventDelivery
from .services import EventService, EventSubscriptionService
from .serializers import (
    EventSerializer, EventCreateSerializer, EventSubscriptionSerializer,
    EventSubscriptionCreateSerializer, EventDeliverySerializer,
    EventStatsSerializer, EventSearchSerializer
)


class EventListCreateView(generics.ListCreateAPIView):
    """List and create events"""
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['event_type', 'source_service', 'target_service', 'status']
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return EventCreateSerializer
        return EventSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by service if specified
        service = self.request.query_params.get('service')
        if service:
            queryset = queryset.filter(
                Q(source_service=service) | Q(target_service=service)
            )
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset.order_by('-created_at')


class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete events"""
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return EventCreateSerializer
        return EventSerializer


class EventSubscriptionListCreateView(generics.ListCreateAPIView):
    """List and create event subscriptions"""
    queryset = EventSubscription.objects.all()
    serializer_class = EventSubscriptionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['subscriber_service', 'event_type', 'source_service', 'is_active']
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return EventSubscriptionCreateSerializer
        return EventSubscriptionSerializer


class EventSubscriptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete event subscriptions"""
    queryset = EventSubscription.objects.all()
    serializer_class = EventSubscriptionSerializer
    permission_classes = [IsAuthenticated]


class EventDeliveryListView(generics.ListAPIView):
    """List event deliveries"""
    queryset = EventDelivery.objects.all()
    serializer_class = EventDeliverySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'event', 'subscription']
    permission_classes = [IsAuthenticated]


class EventDeliveryDetailView(generics.RetrieveAPIView):
    """Retrieve event delivery details"""
    queryset = EventDelivery.objects.all()
    serializer_class = EventDeliverySerializer
    permission_classes = [IsAuthenticated]


class EventStatsView(APIView):
    """Get event statistics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        event_service = EventService()
        stats = event_service.get_event_stats(days)
        
        serializer = EventStatsSerializer(stats)
        return Response(serializer.data)


class EventSearchView(APIView):
    """Search events with advanced filters"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = EventSearchSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = Event.objects.all()
        
        # Apply filters
        if serializer.validated_data.get('event_type'):
            queryset = queryset.filter(event_type=serializer.validated_data['event_type'])
        
        if serializer.validated_data.get('source_service'):
            queryset = queryset.filter(source_service=serializer.validated_data['source_service'])
        
        if serializer.validated_data.get('status'):
            queryset = queryset.filter(status=serializer.validated_data['status'])
        
        if serializer.validated_data.get('start_date'):
            queryset = queryset.filter(created_at__gte=serializer.validated_data['start_date'])
        
        if serializer.validated_data.get('end_date'):
            queryset = queryset.filter(created_at__lte=serializer.validated_data['end_date'])
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        start = (page - 1) * page_size
        end = start + page_size
        
        events = queryset.order_by('-created_at')[start:end]
        serializer = EventSerializer(events, many=True)
        
        return Response({
            'results': serializer.data,
            'total': queryset.count(),
            'page': page,
            'page_size': page_size,
            'pages': (queryset.count() + page_size - 1) // page_size
        })


@api_view(['POST'])
@permission_classes([AllowAny])
def webhook_event_handler(request):
    """Webhook endpoint for receiving events from other services"""
    try:
        event_data = request.data
        
        # Validate required fields
        required_fields = ['event_type', 'source_service', 'data']
        for field in required_fields:
            if field not in event_data:
                return Response(
                    {'error': f'Missing required field: {field}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create event
        event_service = EventService()
        event = event_service.publish_event(
            event_type=event_data['event_type'],
            source_service=event_data['source_service'],
            data=event_data.get('data', {}),
            metadata=event_data.get('metadata', {}),
            target_service=event_data.get('target_service'),
            correlation_id=event_data.get('correlation_id'),
            causation_id=event_data.get('causation_id'),
            priority=event_data.get('priority', 0),
            scheduled_at=event_data.get('scheduled_at'),
            expires_at=event_data.get('expires_at')
        )
        
        return Response({
            'event_id': str(event.id),
            'status': 'created',
            'message': 'Event published successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retry_failed_events(request):
    """Retry failed events"""
    try:
        event_service = EventService()
        max_retries = int(request.data.get('max_retries', 3))
        
        # Get failed events
        failed_events = Event.objects.filter(
            status='failed',
            retry_count__lt=max_retries
        )
        
        retried_count = 0
        for event in failed_events:
            event.increment_retry()
            if event.status == 'retry':
                event_service.process_event(event)
                retried_count += 1
        
        return Response({
            'message': f'Retried {retried_count} failed events',
            'retried_count': retried_count
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cleanup_expired_events(request):
    """Clean up expired events"""
    try:
        event_service = EventService()
        event_service.cleanup_expired_events()
        
        return Response({
            'message': 'Expired events cleaned up successfully'
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint for the events service"""
    return Response({
        'status': 'healthy',
        'service': 'events',
        'timestamp': timezone.now().isoformat(),
        'endpoints': {
            'events': '/api/events/',
            'subscriptions': '/api/events/subscriptions/',
            'webhook': '/api/events/webhook/',
            'stats': '/api/events/stats/',
            'health': '/api/events/health/'
        }
    }, status=status.HTTP_200_OK)


class EventProcessorView(APIView):
    """Process pending events"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            event_service = EventService()
            
            # Get pending events
            service_name = request.data.get('service_name')
            event_type = request.data.get('event_type')
            limit = int(request.data.get('limit', 100))
            
            pending_events = event_service.get_pending_events(
                service_name=service_name,
                event_type=event_type,
                limit=limit
            )
            
            processed_count = 0
            for event in pending_events:
                try:
                    event_service.process_event(event)
                    processed_count += 1
                except Exception as e:
                    # Log error but continue processing other events
                    print(f"Error processing event {event.id}: {e}")
            
            return Response({
                'message': f'Processed {processed_count} events',
                'processed_count': processed_count,
                'total_pending': pending_events.count()
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
