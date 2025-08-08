import uuid
import json
import time
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Avg, Max, Min, Sum
from django.contrib.contenttypes.models import ContentType
from .models import (
    AuditLog, SecurityEvent, PerformanceMetric, DataChangeLog,
    APIAuditLog, DistributedTrace, AuditConfiguration
)


class AuditService:
    """Core service for audit logging functionality"""
    
    @staticmethod
    def log_event(
        level='info',
        log_type='system_event',
        service_name='audit',
        user_id=None,
        session_id=None,
        request_id=None,
        trace_id=None,
        span_id=None,
        ip_address=None,
        user_agent=None,
        request_method=None,
        request_path=None,
        request_params=None,
        request_headers=None,
        request_body=None,
        response_status=None,
        response_time_ms=None,
        response_size=None,
        response_body=None,
        action=None,
        resource_type=None,
        resource_id=None,
        old_values=None,
        new_values=None,
        changed_fields=None,
        message='',
        details=None,
        metadata=None,
        error_type=None,
        error_message=None,
        stack_trace=None
    ):
        """Create an audit log entry"""
        try:
            # Check if audit logging is enabled for this service
            config = AuditConfiguration.objects.filter(
                service_name=service_name,
                enabled=True
            ).first()
            
            if not config:
                return False, "Audit logging not enabled for this service"
            
            # Check log level
            if config.log_level == 'error' and level not in ['error', 'critical']:
                return False, "Log level too low for this configuration"
            
            # Check log types
            if config.log_types and log_type not in config.log_types:
                return False, "Log type not enabled for this configuration"
            
            # Mask sensitive data
            if config.mask_sensitive_fields:
                request_headers = AuditService._mask_sensitive_data(
                    request_headers, config.mask_sensitive_fields
                )
                request_body = AuditService._mask_sensitive_data(
                    request_body, config.mask_sensitive_fields
                )
                response_body = AuditService._mask_sensitive_data(
                    response_body, config.mask_sensitive_fields
                )
            
            # Create audit log entry
            audit_log = AuditLog.objects.create(
                level=level,
                log_type=log_type,
                service_name=service_name,
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
                trace_id=trace_id,
                span_id=span_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_method=request_method,
                request_path=request_path,
                request_params=request_params or {},
                request_headers=request_headers or {},
                request_body=request_body or '',
                response_status=response_status,
                response_time_ms=response_time_ms,
                response_size=response_size,
                response_body=response_body or '',
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                old_values=old_values or {},
                new_values=new_values or {},
                changed_fields=changed_fields or [],
                message=message,
                details=details or {},
                metadata=metadata or {},
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace
            )
            
            return True, audit_log
            
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def _mask_sensitive_data(data, sensitive_fields):
        """Mask sensitive data in request/response bodies"""
        if not data or not sensitive_fields:
            return data
        
        try:
            if isinstance(data, str):
                data_dict = json.loads(data)
            else:
                data_dict = data
            
            for field in sensitive_fields:
                if field in data_dict:
                    data_dict[field] = '***MASKED***'
            
            return json.dumps(data_dict) if isinstance(data, str) else data_dict
        except:
            return data
    
    @staticmethod
    def search_logs(filters):
        """Search audit logs with filters"""
        queryset = AuditLog.objects.all()
        
        if filters.get('service_name'):
            queryset = queryset.filter(service_name=filters['service_name'])
        
        if filters.get('user_id'):
            queryset = queryset.filter(user_id=filters['user_id'])
        
        if filters.get('log_type'):
            queryset = queryset.filter(log_type=filters['log_type'])
        
        if filters.get('level'):
            queryset = queryset.filter(level=filters['level'])
        
        if filters.get('start_date'):
            queryset = queryset.filter(timestamp__gte=filters['start_date'])
        
        if filters.get('end_date'):
            queryset = queryset.filter(timestamp__lte=filters['end_date'])
        
        if filters.get('trace_id'):
            queryset = queryset.filter(trace_id=filters['trace_id'])
        
        if filters.get('request_id'):
            queryset = queryset.filter(request_id=filters['request_id'])
        
        if filters.get('action'):
            queryset = queryset.filter(action=filters['action'])
        
        if filters.get('resource_type'):
            queryset = queryset.filter(resource_type=filters['resource_type'])
        
        if filters.get('resource_id'):
            queryset = queryset.filter(resource_id=filters['resource_id'])
        
        limit = filters.get('limit', 100)
        offset = filters.get('offset', 0)
        
        return queryset[offset:offset + limit]
    
    @staticmethod
    def get_audit_stats(start_date=None, end_date=None, service_name=None):
        """Get audit statistics"""
        queryset = AuditLog.objects.all()
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        if service_name:
            queryset = queryset.filter(service_name=service_name)
        
        stats = {
            'total_logs': queryset.count(),
            'logs_by_level': dict(queryset.values('level').annotate(count=Count('id')).values_list('level', 'count')),
            'logs_by_type': dict(queryset.values('log_type').annotate(count=Count('id')).values_list('log_type', 'count')),
            'logs_by_service': dict(queryset.values('service_name').annotate(count=Count('id')).values_list('service_name', 'count')),
            'recent_errors': list(queryset.filter(level__in=['error', 'critical']).order_by('-timestamp')[:10]),
            'performance_summary': {
                'avg_response_time': queryset.filter(response_time_ms__isnull=False).aggregate(avg=Avg('response_time_ms'))['avg'] or 0,
                'max_response_time': queryset.filter(response_time_ms__isnull=False).aggregate(max=Max('response_time_ms'))['max'] or 0,
                'total_requests': queryset.filter(log_type='api_call').count(),
            }
        }
        
        return stats


class SecurityEventService:
    """Service for security event management"""
    
    @staticmethod
    def create_security_event(
        event_type,
        severity='medium',
        user_id=None,
        ip_address=None,
        user_agent=None,
        session_id=None,
        description='',
        details=None,
        metadata=None,
        risk_score=0,
        risk_factors=None
    ):
        """Create a security event"""
        try:
            security_event = SecurityEvent.objects.create(
                event_type=event_type,
                severity=severity,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent or '',
                session_id=session_id or '',
                description=description,
                details=details or {},
                metadata=metadata or {},
                risk_score=risk_score,
                risk_factors=risk_factors or []
            )
            
            # Check if alerts should be sent
            config = AuditConfiguration.objects.filter(
                alert_on_security_events=True
            ).first()
            
            if config and severity in ['high', 'critical']:
                # TODO: Send alert notification
                pass
            
            return True, security_event
            
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def search_security_events(filters):
        """Search security events with filters"""
        queryset = SecurityEvent.objects.all()
        
        if filters.get('event_type'):
            queryset = queryset.filter(event_type=filters['event_type'])
        
        if filters.get('severity'):
            queryset = queryset.filter(severity=filters['severity'])
        
        if filters.get('user_id'):
            queryset = queryset.filter(user_id=filters['user_id'])
        
        if filters.get('ip_address'):
            queryset = queryset.filter(ip_address=filters['ip_address'])
        
        if filters.get('is_resolved') is not None:
            queryset = queryset.filter(is_resolved=filters['is_resolved'])
        
        if filters.get('start_date'):
            queryset = queryset.filter(timestamp__gte=filters['start_date'])
        
        if filters.get('end_date'):
            queryset = queryset.filter(timestamp__lte=filters['end_date'])
        
        if filters.get('risk_score_min'):
            queryset = queryset.filter(risk_score__gte=filters['risk_score_min'])
        
        if filters.get('risk_score_max'):
            queryset = queryset.filter(risk_score__lte=filters['risk_score_max'])
        
        limit = filters.get('limit', 100)
        offset = filters.get('offset', 0)
        
        return queryset[offset:offset + limit]
    
    @staticmethod
    def get_security_stats(start_date=None, end_date=None):
        """Get security event statistics"""
        queryset = SecurityEvent.objects.all()
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        stats = {
            'total_events': queryset.count(),
            'events_by_type': dict(queryset.values('event_type').annotate(count=Count('id')).values_list('event_type', 'count')),
            'events_by_severity': dict(queryset.values('severity').annotate(count=Count('id')).values_list('severity', 'count')),
            'events_by_ip': dict(queryset.values('ip_address').annotate(count=Count('id')).values_list('ip_address', 'count')),
            'unresolved_events': queryset.filter(is_resolved=False).count(),
            'high_risk_events': queryset.filter(risk_score__gte=70).count(),
        }
        
        return stats


class PerformanceMonitoringService:
    """Service for performance monitoring"""
    
    @staticmethod
    def record_metric(
        service_name,
        metric_type,
        metric_name,
        value,
        unit=None,
        endpoint=None,
        method=None,
        user_id=None,
        session_id=None,
        tags=None,
        metadata=None
    ):
        """Record a performance metric"""
        try:
            metric = PerformanceMetric.objects.create(
                service_name=service_name,
                metric_type=metric_type,
                metric_name=metric_name,
                value=value,
                unit=unit or '',
                endpoint=endpoint or '',
                method=method or '',
                user_id=user_id,
                session_id=session_id or '',
                tags=tags or {},
                metadata=metadata or {}
            )
            
            return True, metric
            
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def get_performance_stats(start_date=None, end_date=None, service_name=None):
        """Get performance statistics"""
        queryset = PerformanceMetric.objects.all()
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        if service_name:
            queryset = queryset.filter(service_name=service_name)
        
        response_time_metrics = queryset.filter(metric_type='response_time')
        
        stats = {
            'avg_response_time': response_time_metrics.aggregate(avg=Avg('value'))['avg'] or 0,
            'max_response_time': response_time_metrics.aggregate(max=Max('value'))['max'] or 0,
            'min_response_time': response_time_metrics.aggregate(min=Min('value'))['min'] or 0,
            'total_requests': queryset.filter(metric_type='throughput').aggregate(sum=Sum('value'))['sum'] or 0,
            'error_rate': queryset.filter(metric_type='error_rate').aggregate(avg=Avg('value'))['avg'] or 0,
            'throughput': queryset.filter(metric_type='throughput').aggregate(avg=Avg('value'))['avg'] or 0,
            'metrics_by_service': dict(queryset.values('service_name').annotate(count=Count('id')).values_list('service_name', 'count')),
        }
        
        return stats


class DistributedTracingService:
    """Service for distributed tracing"""
    
    @staticmethod
    def start_trace(
        trace_id=None,
        parent_span_id=None,
        service_name='audit',
        operation_name='unknown',
        user_id=None,
        session_id=None,
        request_id=None,
        tags=None,
        metadata=None
    ):
        """Start a new trace span"""
        try:
            if not trace_id:
                trace_id = uuid.uuid4()
            
            span_id = uuid.uuid4()
            
            trace = DistributedTrace.objects.create(
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                span_id=span_id,
                service_name=service_name,
                operation_name=operation_name,
                start_time=timezone.now(),
                status='active',
                user_id=user_id,
                session_id=session_id or '',
                request_id=request_id,
                tags=tags or {},
                metadata=metadata or {}
            )
            
            return True, trace
            
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def end_trace(span_id, status='completed', error_type=None, error_message=None, stack_trace=None):
        """End a trace span"""
        try:
            trace = DistributedTrace.objects.get(span_id=span_id)
            trace.end_time = timezone.now()
            trace.duration_ms = int((trace.end_time - trace.start_time).total_seconds() * 1000)
            trace.status = status
            trace.error_type = error_type
            trace.error_message = error_message
            trace.stack_trace = stack_trace
            trace.save()
            
            return True, trace
            
        except DistributedTrace.DoesNotExist:
            return False, "Trace not found"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def get_trace_tree(trace_id):
        """Get complete trace tree for a trace ID"""
        traces = DistributedTrace.objects.filter(trace_id=trace_id).order_by('start_time')
        
        if not traces:
            return None
        
        # Build trace tree
        trace_tree = {
            'trace_id': trace_id,
            'spans': [],
            'total_duration': 0,
            'status': 'completed'
        }
        
        for trace in traces:
            span = {
                'span_id': trace.span_id,
                'parent_span_id': trace.parent_span_id,
                'service_name': trace.service_name,
                'operation_name': trace.operation_name,
                'start_time': trace.start_time,
                'end_time': trace.end_time,
                'duration_ms': trace.duration_ms,
                'status': trace.status,
                'tags': trace.tags,
                'metadata': trace.metadata,
                'error_type': trace.error_type,
                'error_message': trace.error_message,
            }
            trace_tree['spans'].append(span)
            
            if trace.duration_ms:
                trace_tree['total_duration'] += trace.duration_ms
            
            if trace.status == 'failed':
                trace_tree['status'] = 'failed'
        
        return trace_tree
    
    @staticmethod
    def get_trace_stats(start_date=None, end_date=None, service_name=None):
        """Get distributed trace statistics"""
        queryset = DistributedTrace.objects.all()
        
        if start_date:
            queryset = queryset.filter(start_time__gte=start_date)
        if end_date:
            queryset = queryset.filter(start_time__lte=end_date)
        if service_name:
            queryset = queryset.filter(service_name=service_name)
        
        completed_traces = queryset.filter(status='completed')
        failed_traces = queryset.filter(status='failed')
        
        stats = {
            'total_traces': queryset.count(),
            'active_traces': queryset.filter(status='active').count(),
            'completed_traces': completed_traces.count(),
            'failed_traces': failed_traces.count(),
            'avg_duration': completed_traces.aggregate(avg=Avg('duration_ms'))['avg'] or 0,
            'max_duration': completed_traces.aggregate(max=Max('duration_ms'))['max'] or 0,
            'traces_by_service': dict(queryset.values('service_name').annotate(count=Count('id')).values_list('service_name', 'count')),
        }
        
        return stats


class DataChangeTrackingService:
    """Service for tracking data changes"""
    
    @staticmethod
    def track_data_change(
        user_id=None,
        service_name='audit',
        change_type='update',
        model_name=None,
        object_id=None,
        content_type=None,
        old_values=None,
        new_values=None,
        changed_fields=None,
        request_id=None,
        session_id=None,
        ip_address=None,
        reason=None,
        metadata=None
    ):
        """Track a data change"""
        try:
            change_log = DataChangeLog.objects.create(
                user_id=user_id,
                service_name=service_name,
                change_type=change_type,
                model_name=model_name or '',
                object_id=object_id,
                content_type=content_type,
                old_values=old_values or {},
                new_values=new_values or {},
                changed_fields=changed_fields or [],
                request_id=request_id,
                session_id=session_id or '',
                ip_address=ip_address,
                reason=reason or '',
                metadata=metadata or {}
            )
            
            return True, change_log
            
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def get_change_history(object_id, content_type, limit=50):
        """Get change history for a specific object"""
        return DataChangeLog.objects.filter(
            object_id=object_id,
            content_type=content_type
        ).order_by('-timestamp')[:limit]


class APIAuditService:
    """Service for API call auditing"""
    
    @staticmethod
    def log_api_call(
        service_name,
        endpoint,
        method,
        user_id=None,
        session_id=None,
        request_id=None,
        trace_id=None,
        span_id=None,
        ip_address=None,
        user_agent=None,
        referer=None,
        request_headers=None,
        request_params=None,
        request_body=None,
        request_size=None,
        response_status=None,
        response_time_ms=None,
        response_size=None,
        response_body=None,
        error_type=None,
        error_message=None,
        stack_trace=None,
        database_queries=0,
        cache_hits=0,
        cache_misses=0,
        metadata=None
    ):
        """Log an API call"""
        try:
            # Determine status category
            status_category = '2xx'
            if response_status:
                if 300 <= response_status < 400:
                    status_category = '3xx'
                elif 400 <= response_status < 500:
                    status_category = '4xx'
                elif 500 <= response_status < 600:
                    status_category = '5xx'
            
            api_log = APIAuditLog.objects.create(
                service_name=service_name,
                endpoint=endpoint,
                method=method,
                user_id=user_id,
                session_id=session_id or '',
                request_id=request_id,
                trace_id=trace_id,
                span_id=span_id,
                ip_address=ip_address,
                user_agent=user_agent or '',
                referer=referer or '',
                request_headers=request_headers or {},
                request_params=request_params or {},
                request_body=request_body or '',
                request_size=request_size,
                response_status=response_status,
                status_category=status_category,
                response_time_ms=response_time_ms,
                response_size=response_size,
                response_body=response_body or '',
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace,
                database_queries=database_queries,
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                metadata=metadata or {}
            )
            
            return True, api_log
            
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def get_api_stats(start_date=None, end_date=None, service_name=None):
        """Get API call statistics"""
        queryset = APIAuditLog.objects.all()
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        if service_name:
            queryset = queryset.filter(service_name=service_name)
        
        stats = {
            'total_calls': queryset.count(),
            'calls_by_method': dict(queryset.values('method').annotate(count=Count('id')).values_list('method', 'count')),
            'calls_by_status': dict(queryset.values('status_category').annotate(count=Count('id')).values_list('status_category', 'count')),
            'calls_by_service': dict(queryset.values('service_name').annotate(count=Count('id')).values_list('service_name', 'count')),
            'avg_response_time': queryset.aggregate(avg=Avg('response_time_ms'))['avg'] or 0,
            'max_response_time': queryset.aggregate(max=Max('response_time_ms'))['max'] or 0,
            'error_rate': queryset.filter(status_category='5xx').count() / max(queryset.count(), 1) * 100,
            'total_database_queries': queryset.aggregate(sum=Sum('database_queries'))['sum'] or 0,
            'cache_hit_rate': queryset.aggregate(avg=Avg('cache_hits')).get('avg', 0) / max(queryset.aggregate(avg=Avg('cache_hits')).get('avg', 0) + queryset.aggregate(avg=Avg('cache_misses')).get('avg', 0), 1) * 100,
        }
        
        return stats
