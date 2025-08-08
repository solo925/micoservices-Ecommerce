import uuid
import time
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min, Sum
from rest_framework import status, permissions, generics, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.contenttypes.models import ContentType

from .models import (
    AuditLog, SecurityEvent, PerformanceMetric, DataChangeLog,
    APIAuditLog, DistributedTrace, AuditConfiguration
)
from .serializers import (
    AuditLogSerializer, AuditLogCreateSerializer, AuditLogSearchSerializer,
    SecurityEventSerializer, SecurityEventCreateSerializer, SecurityEventUpdateSerializer, SecurityEventSearchSerializer,
    PerformanceMetricSerializer, PerformanceMetricCreateSerializer, PerformanceMetricSearchSerializer,
    DataChangeLogSerializer, DataChangeLogCreateSerializer, DataChangeLogSearchSerializer,
    APIAuditLogSerializer, APIAuditLogCreateSerializer, APIAuditLogSearchSerializer,
    DistributedTraceSerializer, DistributedTraceCreateSerializer, DistributedTraceUpdateSerializer, DistributedTraceSearchSerializer,
    AuditConfigurationSerializer, AuditConfigurationCreateSerializer, AuditConfigurationUpdateSerializer,
    AuditStatsSerializer, SecurityEventStatsSerializer, PerformanceStatsSerializer, TraceStatsSerializer,
    AuditExportSerializer, AuditAlertSerializer
)
from .services import (
    AuditService, SecurityEventService, PerformanceMonitoringService,
    DistributedTracingService, DataChangeTrackingService, APIAuditService
)


# Audit Log Views
class AuditLogListCreateView(generics.ListCreateAPIView):
    """List and create audit logs"""
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['service_name', 'log_type', 'level', 'user_id']
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AuditLogCreateSerializer
        return AuditLogSerializer


class AuditLogDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete audit logs"""
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'


class AuditLogSearchView(APIView):
    """Search audit logs with advanced filters"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = AuditLogSearchSerializer(data=request.data)
        if serializer.is_valid():
            filters = serializer.validated_data
            logs = AuditService.search_logs(filters)
            serializer = AuditLogSerializer(logs, many=True)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AuditLogStatsView(APIView):
    """Get audit log statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        service_name = request.query_params.get('service_name')
        
        if start_date:
            start_date = timezone.datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_date = timezone.datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        stats = AuditService.get_audit_stats(start_date, end_date, service_name)
        serializer = AuditStatsSerializer(stats)
        return Response(serializer.data)


# Security Event Views
class SecurityEventListCreateView(generics.ListCreateAPIView):
    """List and create security events"""
    queryset = SecurityEvent.objects.all()
    serializer_class = SecurityEventSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['event_type', 'severity', 'user_id', 'ip_address', 'is_resolved']
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SecurityEventCreateSerializer
        return SecurityEventSerializer


class SecurityEventDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete security events"""
    queryset = SecurityEvent.objects.all()
    serializer_class = SecurityEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return SecurityEventUpdateSerializer
        return SecurityEventSerializer


class SecurityEventSearchView(APIView):
    """Search security events with advanced filters"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = SecurityEventSearchSerializer(data=request.data)
        if serializer.is_valid():
            filters = serializer.validated_data
            events = SecurityEventService.search_security_events(filters)
            serializer = SecurityEventSerializer(events, many=True)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SecurityEventStatsView(APIView):
    """Get security event statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            start_date = timezone.datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_date = timezone.datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        stats = SecurityEventService.get_security_stats(start_date, end_date)
        serializer = SecurityEventStatsSerializer(stats)
        return Response(serializer.data)


# Performance Metric Views
class PerformanceMetricListCreateView(generics.ListCreateAPIView):
    """List and create performance metrics"""
    queryset = PerformanceMetric.objects.all()
    serializer_class = PerformanceMetricSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['service_name', 'metric_type', 'metric_name']
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PerformanceMetricCreateSerializer
        return PerformanceMetricSerializer


class PerformanceMetricDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete performance metrics"""
    queryset = PerformanceMetric.objects.all()
    serializer_class = PerformanceMetricSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'


class PerformanceMetricSearchView(APIView):
    """Search performance metrics with advanced filters"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = PerformanceMetricSearchSerializer(data=request.data)
        if serializer.is_valid():
            filters = serializer.validated_data
            metrics = PerformanceMetric.objects.filter(
                **{k: v for k, v in filters.items() if v is not None}
            )
            serializer = PerformanceMetricSerializer(metrics, many=True)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PerformanceMetricStatsView(APIView):
    """Get performance metric statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        service_name = request.query_params.get('service_name')
        
        if start_date:
            start_date = timezone.datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_date = timezone.datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        stats = PerformanceMonitoringService.get_performance_stats(start_date, end_date, service_name)
        serializer = PerformanceStatsSerializer(stats)
        return Response(serializer.data)


# Data Change Log Views
class DataChangeLogListCreateView(generics.ListCreateAPIView):
    """List and create data change logs"""
    queryset = DataChangeLog.objects.all()
    serializer_class = DataChangeLogSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['service_name', 'change_type', 'model_name', 'user_id']
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DataChangeLogCreateSerializer
        return DataChangeLogSerializer


class DataChangeLogDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete data change logs"""
    queryset = DataChangeLog.objects.all()
    serializer_class = DataChangeLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'


class DataChangeLogSearchView(APIView):
    """Search data change logs with advanced filters"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = DataChangeLogSearchSerializer(data=request.data)
        if serializer.is_valid():
            filters = serializer.validated_data
            logs = DataChangeLog.objects.filter(
                **{k: v for k, v in filters.items() if v is not None}
            )
            serializer = DataChangeLogSerializer(logs, many=True)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DataChangeHistoryView(APIView):
    """Get change history for a specific object"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, object_id, content_type_id):
        try:
            content_type = ContentType.objects.get(id=content_type_id)
            history = DataChangeTrackingService.get_change_history(object_id, content_type)
            serializer = DataChangeLogSerializer(history, many=True)
            return Response(serializer.data)
        except ContentType.DoesNotExist:
            return Response({'error': 'Content type not found'}, status=status.HTTP_404_NOT_FOUND)


# API Audit Log Views
class APIAuditLogListCreateView(generics.ListCreateAPIView):
    """List and create API audit logs"""
    queryset = APIAuditLog.objects.all()
    serializer_class = APIAuditLogSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['service_name', 'method', 'response_status', 'status_category']
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return APIAuditLogCreateSerializer
        return APIAuditLogSerializer


class APIAuditLogDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete API audit logs"""
    queryset = APIAuditLog.objects.all()
    serializer_class = APIAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'


class APIAuditLogSearchView(APIView):
    """Search API audit logs with advanced filters"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = APIAuditLogSearchSerializer(data=request.data)
        if serializer.is_valid():
            filters = serializer.validated_data
            logs = APIAuditLog.objects.filter(
                **{k: v for k, v in filters.items() if v is not None}
            )
            serializer = APIAuditLogSerializer(logs, many=True)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class APIAuditLogStatsView(APIView):
    """Get API audit log statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        service_name = request.query_params.get('service_name')
        
        if start_date:
            start_date = timezone.datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_date = timezone.datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        stats = APIAuditService.get_api_stats(start_date, end_date, service_name)
        return Response(stats)


# Distributed Trace Views
class DistributedTraceListCreateView(generics.ListCreateAPIView):
    """List and create distributed traces"""
    queryset = DistributedTrace.objects.all()
    serializer_class = DistributedTraceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['service_name', 'status', 'trace_id']
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DistributedTraceCreateSerializer
        return DistributedTraceSerializer


class DistributedTraceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete distributed traces"""
    queryset = DistributedTrace.objects.all()
    serializer_class = DistributedTraceSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return DistributedTraceUpdateSerializer
        return DistributedTraceSerializer


class DistributedTraceSearchView(APIView):
    """Search distributed traces with advanced filters"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = DistributedTraceSearchSerializer(data=request.data)
        if serializer.is_valid():
            filters = serializer.validated_data
            traces = DistributedTrace.objects.filter(
                **{k: v for k, v in filters.items() if v is not None}
            )
            serializer = DistributedTraceSerializer(traces, many=True)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DistributedTraceTreeView(APIView):
    """Get complete trace tree for a trace ID"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, trace_id):
        trace_tree = DistributedTracingService.get_trace_tree(trace_id)
        if trace_tree:
            return Response(trace_tree)
        return Response({'error': 'Trace not found'}, status=status.HTTP_404_NOT_FOUND)


class DistributedTraceStatsView(APIView):
    """Get distributed trace statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        service_name = request.query_params.get('service_name')
        
        if start_date:
            start_date = timezone.datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_date = timezone.datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        stats = DistributedTracingService.get_trace_stats(start_date, end_date, service_name)
        serializer = TraceStatsSerializer(stats)
        return Response(serializer.data)


# Audit Configuration Views
class AuditConfigurationListCreateView(generics.ListCreateAPIView):
    """List and create audit configurations"""
    queryset = AuditConfiguration.objects.all()
    serializer_class = AuditConfigurationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AuditConfigurationCreateSerializer
        return AuditConfigurationSerializer


class AuditConfigurationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete audit configurations"""
    queryset = AuditConfiguration.objects.all()
    serializer_class = AuditConfigurationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AuditConfigurationUpdateSerializer
        return AuditConfigurationSerializer


# Utility Views
class StartTraceView(APIView):
    """Start a new distributed trace"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        trace_id = request.data.get('trace_id')
        parent_span_id = request.data.get('parent_span_id')
        service_name = request.data.get('service_name', 'audit')
        operation_name = request.data.get('operation_name', 'unknown')
        user_id = request.data.get('user_id')
        session_id = request.data.get('session_id')
        request_id = request.data.get('request_id')
        tags = request.data.get('tags', {})
        metadata = request.data.get('metadata', {})
        
        success, result = DistributedTracingService.start_trace(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            service_name=service_name,
            operation_name=operation_name,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            tags=tags,
            metadata=metadata
        )
        
        if success:
            serializer = DistributedTraceSerializer(result)
            return Response(serializer.data)
        else:
            return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


class EndTraceView(APIView):
    """End a distributed trace"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        span_id = request.data.get('span_id')
        status = request.data.get('status', 'completed')
        error_type = request.data.get('error_type')
        error_message = request.data.get('error_message')
        stack_trace = request.data.get('stack_trace')
        
        success, result = DistributedTracingService.end_trace(
            span_id=span_id,
            status=status,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace
        )
        
        if success:
            serializer = DistributedTraceSerializer(result)
            return Response(serializer.data)
        else:
            return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


class RecordMetricView(APIView):
    """Record a performance metric"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        service_name = request.data.get('service_name')
        metric_type = request.data.get('metric_type')
        metric_name = request.data.get('metric_name')
        value = request.data.get('value')
        unit = request.data.get('unit')
        endpoint = request.data.get('endpoint')
        method = request.data.get('method')
        user_id = request.data.get('user_id')
        session_id = request.data.get('session_id')
        tags = request.data.get('tags', {})
        metadata = request.data.get('metadata', {})
        
        success, result = PerformanceMonitoringService.record_metric(
            service_name=service_name,
            metric_type=metric_type,
            metric_name=metric_name,
            value=value,
            unit=unit,
            endpoint=endpoint,
            method=method,
            user_id=user_id,
            session_id=session_id,
            tags=tags,
            metadata=metadata
        )
        
        if success:
            serializer = PerformanceMetricSerializer(result)
            return Response(serializer.data)
        else:
            return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


class LogSecurityEventView(APIView):
    """Log a security event"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        event_type = request.data.get('event_type')
        severity = request.data.get('severity', 'medium')
        user_id = request.data.get('user_id')
        ip_address = request.data.get('ip_address')
        user_agent = request.data.get('user_agent')
        session_id = request.data.get('session_id')
        description = request.data.get('description', '')
        details = request.data.get('details', {})
        metadata = request.data.get('metadata', {})
        risk_score = request.data.get('risk_score', 0)
        risk_factors = request.data.get('risk_factors', [])
        
        success, result = SecurityEventService.create_security_event(
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            description=description,
            details=details,
            metadata=metadata,
            risk_score=risk_score,
            risk_factors=risk_factors
        )
        
        if success:
            serializer = SecurityEventSerializer(result)
            return Response(serializer.data)
        else:
            return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


class LogAPICallView(APIView):
    """Log an API call"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        service_name = request.data.get('service_name')
        endpoint = request.data.get('endpoint')
        method = request.data.get('method')
        user_id = request.data.get('user_id')
        session_id = request.data.get('session_id')
        request_id = request.data.get('request_id')
        trace_id = request.data.get('trace_id')
        span_id = request.data.get('span_id')
        ip_address = request.data.get('ip_address')
        user_agent = request.data.get('user_agent')
        referer = request.data.get('referer')
        request_headers = request.data.get('request_headers', {})
        request_params = request.data.get('request_params', {})
        request_body = request.data.get('request_body')
        request_size = request.data.get('request_size')
        response_status = request.data.get('response_status')
        response_time_ms = request.data.get('response_time_ms')
        response_size = request.data.get('response_size')
        response_body = request.data.get('response_body')
        error_type = request.data.get('error_type')
        error_message = request.data.get('error_message')
        stack_trace = request.data.get('stack_trace')
        database_queries = request.data.get('database_queries', 0)
        cache_hits = request.data.get('cache_hits', 0)
        cache_misses = request.data.get('cache_misses', 0)
        metadata = request.data.get('metadata', {})
        
        success, result = APIAuditService.log_api_call(
            service_name=service_name,
            endpoint=endpoint,
            method=method,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            trace_id=trace_id,
            span_id=span_id,
            ip_address=ip_address,
            user_agent=user_agent,
            referer=referer,
            request_headers=request_headers,
            request_params=request_params,
            request_body=request_body,
            request_size=request_size,
            response_status=response_status,
            response_time_ms=response_time_ms,
            response_size=response_size,
            response_body=response_body,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            database_queries=database_queries,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            metadata=metadata
        )
        
        if success:
            serializer = APIAuditLogSerializer(result)
            return Response(serializer.data)
        else:
            return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'service': 'audit',
        'timestamp': timezone.now().isoformat()
    }, status=status.HTTP_200_OK)
