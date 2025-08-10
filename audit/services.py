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
    
    # Class-level cache for configurations to avoid repeated DB queries
    _config_cache = {}
    _cache_ttl = 300  # 5 minutes cache TTL
    
    @classmethod
    def _get_cached_config(cls, service_name):
        """Get cached configuration or fetch from database"""
        from django.utils import timezone
        
        now = timezone.now()
        cache_key = f"{service_name}_{now.timestamp() // cls._cache_ttl}"
        
        if cache_key in cls._config_cache:
            return cls._config_cache[cache_key]
        
        # Fetch from database and cache
        config = AuditConfiguration.objects.filter(
            service_name=service_name,
            enabled=True
        ).first()
        
        cls._config_cache[cache_key] = config
        return config
    
    @classmethod
    def clear_config_cache(cls):
        """Clear the configuration cache"""
        cls._config_cache.clear()
    
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
        """Create an audit log entry with optimized configuration lookup"""
        try:
            # Check if audit logging is enabled for this service using cached config
            config = AuditService._get_cached_config(service_name)
            
            if not config:
                return False, "Audit logging not enabled for this service"
            
            # Check log level and type in single condition
            if (config.log_level == 'error' and level not in ['error', 'critical']) or \
               (config.log_types and log_type not in config.log_types):
                return False, "Log level too low or log type not enabled for this configuration"
            
            # Mask sensitive data efficiently
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
            
            # Create audit log entry with bulk field assignment
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
    def bulk_log_events(events_data):
        """Bulk create audit log entries for better performance"""
        try:
            # Validate all events first
            valid_events = []
            for event_data in events_data:
                # Check configuration for each service
                service_name = event_data.get('service_name', 'audit')
                config = AuditService._get_cached_config(service_name)
                
                if not config:
                    continue  # Skip events for disabled services
                
                # Apply configuration checks
                level = event_data.get('level', 'info')
                log_type = event_data.get('log_type', 'system_event')
                
                if (config.log_level == 'error' and level not in ['error', 'critical']) or \
                   (config.log_types and log_type not in config.log_types):
                    continue  # Skip events that don't meet criteria
                
                # Mask sensitive data if needed
                if config.mask_sensitive_fields:
                    event_data['request_headers'] = AuditService._mask_sensitive_data(
                        event_data.get('request_headers'), config.mask_sensitive_fields
                    )
                    event_data['request_body'] = AuditService._mask_sensitive_data(
                        event_data.get('request_body'), config.mask_sensitive_fields
                    )
                    event_data['response_body'] = AuditService._mask_sensitive_data(
                        event_data.get('response_body'), config.mask_sensitive_fields
                    )
                
                # Prepare event for bulk creation
                event_obj = AuditLog(
                    level=level,
                    log_type=log_type,
                    service_name=service_name,
                    user_id=event_data.get('user_id'),
                    session_id=event_data.get('session_id'),
                    request_id=event_data.get('request_id'),
                    trace_id=event_data.get('trace_id'),
                    span_id=event_data.get('span_id'),
                    ip_address=event_data.get('ip_address'),
                    user_agent=event_data.get('user_agent'),
                    request_method=event_data.get('request_method'),
                    request_path=event_data.get('request_path'),
                    request_params=event_data.get('request_params') or {},
                    request_headers=event_data.get('request_headers') or {},
                    request_body=event_data.get('request_body') or '',
                    response_status=event_data.get('response_status'),
                    response_time_ms=event_data.get('response_time_ms'),
                    response_size=event_data.get('response_size'),
                    response_body=event_data.get('response_body') or '',
                    action=event_data.get('action'),
                    resource_type=event_data.get('resource_type'),
                    resource_id=event_data.get('resource_id'),
                    old_values=event_data.get('old_values') or {},
                    new_values=event_data.get('new_values') or {},
                    changed_fields=event_data.get('changed_fields') or [],
                    message=event_data.get('message', ''),
                    details=event_data.get('details') or {},
                    metadata=event_data.get('metadata') or {},
                    error_type=event_data.get('error_type'),
                    error_message=event_data.get('error_message'),
                    stack_trace=event_data.get('stack_trace')
                )
                valid_events.append(event_obj)
            
            if not valid_events:
                return False, "No valid events to log"
            
            # Bulk create all valid events
            created_events = AuditLog.objects.bulk_create(valid_events)
            
            return True, created_events
            
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
        
        # Define filter mappings for direct field lookups
        direct_filters = {
            'service_name': 'service_name',
            'user_id': 'user_id', 
            'log_type': 'log_type',
            'level': 'level',
            'trace_id': 'trace_id',
            'request_id': 'request_id',
            'action': 'action',
            'resource_type': 'resource_type',
            'resource_id': 'resource_id'
        }
        
        # Apply direct filters using dictionary comprehension
        filter_kwargs = {
            direct_filters[key]: value 
            for key, value in filters.items() 
            if key in direct_filters and value is not None
        }
        
        if filter_kwargs:
            queryset = queryset.filter(**filter_kwargs)
        
        # Handle date range filters separately (they need special operators)
        if filters.get('start_date'):
            queryset = queryset.filter(timestamp__gte=filters['start_date'])
        
        if filters.get('end_date'):
            queryset = queryset.filter(timestamp__lte=filters['end_date'])
        
        # Apply pagination
        limit = filters.get('limit', 100)
        offset = filters.get('offset', 0)
        
        return queryset[offset:offset + limit]
    
    @staticmethod
    def search_logs_optimized(filters, use_indexes=True):
        """Search audit logs with optimized queries considering database indexes"""
        # Start with base queryset
        queryset = AuditLog.objects.all()
        
        # Apply filters in order of most selective to least selective
        # This helps the database query planner use indexes effectively
        
        # High-selectivity filters first (usually have indexes)
        if filters.get('trace_id'):
            queryset = queryset.filter(trace_id=filters['trace_id'])
        
        if filters.get('request_id'):
            queryset = queryset.filter(request_id=filters['request_id'])
        
        if filters.get('user_id'):
            queryset = queryset.filter(user_id=filters['user_id'])
        
        # Medium-selectivity filters
        if filters.get('service_name'):
            queryset = queryset.filter(service_name=filters['service_name'])
        
        if filters.get('log_type'):
            queryset = queryset.filter(log_type=filters['log_type'])
        
        if filters.get('level'):
            queryset = queryset.filter(level=filters['level'])
        
        if filters.get('action'):
            queryset = queryset.filter(action=filters['action'])
        
        if filters.get('resource_type'):
            queryset = queryset.filter(resource_type=filters['resource_type'])
        
        if filters.get('resource_id'):
            queryset = queryset.filter(resource_id=filters['resource_id'])
        
        # Date range filters (usually have indexes on timestamp)
        if filters.get('start_date'):
            queryset = queryset.filter(timestamp__gte=filters['start_date'])
        
        if filters.get('end_date'):
            queryset = queryset.filter(timestamp__lte=filters['end_date'])
        
        # Apply pagination with optimized slicing
        limit = filters.get('limit', 100)
        offset = filters.get('offset', 0)
        
        # Use select_related for foreign key fields if needed
        if use_indexes:
            queryset = queryset.select_related('user_id').only(
                'id', 'timestamp', 'level', 'log_type', 'service_name', 
                'message', 'action', 'resource_type', 'resource_id',
                'trace_id', 'request_id', 'user_id'
            )
        
        return queryset[offset:offset + limit]
    
    @staticmethod
    def get_index_recommendations():
        """Get database index recommendations for optimal performance"""
        return {
            'critical_indexes': [
                'CREATE INDEX idx_auditlog_timestamp ON audit_auditlog(timestamp);',
                'CREATE INDEX idx_auditlog_trace_id ON audit_auditlog(trace_id);',
                'CREATE INDEX idx_auditlog_request_id ON audit_auditlog(request_id);',
                'CREATE INDEX idx_auditlog_user_id ON audit_auditlog(user_id);',
                'CREATE INDEX idx_auditlog_service_name ON audit_auditlog(service_name);',
                'CREATE INDEX idx_auditlog_level ON audit_auditlog(level);',
                'CREATE INDEX idx_auditlog_log_type ON audit_auditlog(log_type);'
            ],
            'composite_indexes': [
                'CREATE INDEX idx_auditlog_service_timestamp ON audit_auditlog(service_name, timestamp);',
                'CREATE INDEX idx_auditlog_user_timestamp ON audit_auditlog(user_id, timestamp);',
                'CREATE INDEX idx_auditlog_level_timestamp ON audit_auditlog(level, timestamp);',
                'CREATE INDEX idx_auditlog_trace_span ON audit_auditlog(trace_id, span_id);'
            ],
            'partial_indexes': [
                'CREATE INDEX idx_auditlog_errors ON audit_auditlog(timestamp) WHERE level IN (\'error\', \'critical\');',
                'CREATE INDEX idx_auditlog_api_calls ON audit_auditlog(timestamp) WHERE log_type = \'api_call\';'
            ],
            'performance_tips': [
                'Use search_logs_optimized() for complex queries',
                'Implement connection pooling for high concurrency',
                'Consider partitioning large audit tables by date',
                'Use bulk_log_events() for high-volume logging',
                'Monitor slow query logs and adjust indexes accordingly'
            ]
        }
    
    @staticmethod
    def get_audit_stats(start_date=None, end_date=None, service_name=None):
        """Get audit statistics with optimized single query"""
        queryset = AuditLog.objects.all()
        
        # Apply filters
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        if service_name:
            queryset = queryset.filter(service_name=service_name)
        
        # Use single optimized query with annotations
        from django.db.models import Case, When, IntegerField
        
        stats_queryset = queryset.aggregate(
            total_logs=Count('id'),
            avg_response_time=Avg('response_time_ms'),
            max_response_time=Max('response_time_ms'),
            total_requests=Count('id', filter=Q(log_type='api_call')),
            error_count=Count('id', filter=Q(level__in=['error', 'critical']))
        )
        
        # Get grouped statistics in single queries
        logs_by_level = dict(
            queryset.values('level').annotate(count=Count('id')).values_list('level', 'count')
        )
        logs_by_type = dict(
            queryset.values('log_type').annotate(count=Count('id')).values_list('log_type', 'count')
        )
        logs_by_service = dict(
            queryset.values('service_name').annotate(count=Count('id')).values_list('service_name', 'count')
        )
        
        # Get recent errors (limit to avoid memory issues)
        recent_errors = list(
            queryset.filter(level__in=['error', 'critical'])
            .order_by('-timestamp')
            .values('id', 'timestamp', 'level', 'message', 'service_name')[:10]
        )
        
        stats = {
            'total_logs': stats_queryset['total_logs'] or 0,
            'logs_by_level': logs_by_level,
            'logs_by_type': logs_by_type,
            'logs_by_service': logs_by_service,
            'recent_errors': recent_errors,
            'performance_summary': {
                'avg_response_time': stats_queryset['avg_response_time'] or 0,
                'max_response_time': stats_queryset['max_response_time'] or 0,
                'total_requests': stats_queryset['total_requests'] or 0,
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
        
        # Define filter mappings for direct field lookups
        direct_filters = {
            'event_type': 'event_type',
            'severity': 'severity',
            'user_id': 'user_id',
            'ip_address': 'ip_address',
            'is_resolved': 'is_resolved'
        }
        
        # Apply direct filters using dictionary comprehension
        filter_kwargs = {
            direct_filters[key]: value 
            for key, value in filters.items() 
            if key in direct_filters and value is not None
        }
        
        if filter_kwargs:
            queryset = queryset.filter(**filter_kwargs)
        
        # Handle date range filters separately (they need special operators)
        if filters.get('start_date'):
            queryset = queryset.filter(timestamp__gte=filters['start_date'])
        
        if filters.get('end_date'):
            queryset = queryset.filter(timestamp__lte=filters['end_date'])
        
        # Handle range filters for risk score
        if filters.get('risk_score_min'):
            queryset = queryset.filter(risk_score__gte=filters['risk_score_min'])
        
        if filters.get('risk_score_max'):
            queryset = queryset.filter(risk_score__lte=filters['risk_score_max'])
        
        # Apply pagination
        limit = filters.get('limit', 100)
        offset = filters.get('offset', 0)
        
        return queryset[offset:offset + limit]
    
    @staticmethod
    def get_security_stats(start_date=None, end_date=None):
        """Get security event statistics with optimized single query"""
        queryset = SecurityEvent.objects.all()
        
        # Apply filters
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        # Use single optimized query with annotations
        stats_queryset = queryset.aggregate(
            total_events=Count('id'),
            unresolved_events=Count('id', filter=Q(is_resolved=False)),
            high_risk_events=Count('id', filter=Q(risk_score__gte=70))
        )
        
        # Get grouped statistics in single queries
        events_by_type = dict(
            queryset.values('event_type').annotate(count=Count('id')).values_list('event_type', 'count')
        )
        events_by_severity = dict(
            queryset.values('severity').annotate(count=Count('id')).values_list('severity', 'count')
        )
        events_by_ip = dict(
            queryset.values('ip_address').annotate(count=Count('id')).values_list('ip_address', 'count')
        )
        
        stats = {
            'total_events': stats_queryset['total_events'] or 0,
            'events_by_type': events_by_type,
            'events_by_severity': events_by_severity,
            'events_by_ip': events_by_ip,
            'unresolved_events': stats_queryset['unresolved_events'] or 0,
            'high_risk_events': stats_queryset['high_risk_events'] or 0,
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
        """Get performance statistics with optimized single query"""
        queryset = PerformanceMetric.objects.all()
        
        # Apply filters
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        if service_name:
            queryset = queryset.filter(service_name=service_name)
        
        # Use single optimized query with annotations for response time metrics
        response_time_metrics = queryset.filter(metric_type='response_time')
        
        # Get all metrics in single optimized queries
        stats_queryset = queryset.aggregate(
            total_metrics=Count('id'),
            throughput_sum=Sum('value', filter=Q(metric_type='throughput')),
            error_rate_avg=Avg('value', filter=Q(metric_type='error_rate'))
        )
        
        response_time_stats = response_time_metrics.aggregate(
            avg_response_time=Avg('value'),
            max_response_time=Max('value'),
            min_response_time=Min('value')
        )
        
        # Get grouped statistics in single query
        metrics_by_service = dict(
            queryset.values('service_name').annotate(count=Count('id')).values_list('service_name', 'count')
        )
        
        stats = {
            'avg_response_time': response_time_stats['avg_response_time'] or 0,
            'max_response_time': response_time_stats['max_response_time'] or 0,
            'min_response_time': response_time_stats['min_response_time'] or 0,
            'total_requests': stats_queryset['throughput_sum'] or 0,
            'error_rate': stats_queryset['error_rate_avg'] or 0,
            'throughput': stats_queryset['throughput_sum'] or 0,
            'metrics_by_service': metrics_by_service,
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
        """Get complete trace tree for a trace ID with optimized queries"""
        # Use select_related to fetch related data in single query
        traces = DistributedTrace.objects.filter(trace_id=trace_id).order_by('start_time')
        
        if not traces:
            return None
        
        # Build trace tree with optimized data access
        trace_tree = {
            'trace_id': trace_id,
            'spans': [],
            'total_duration': 0,
            'status': 'completed'
        }
        
        # Process traces efficiently
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
            
            # Update tree statistics
            if trace.duration_ms:
                trace_tree['total_duration'] += trace.duration_ms
            
            if trace.status == 'failed':
                trace_tree['status'] = 'failed'
        
        return trace_tree
    
    @staticmethod
    def get_trace_stats(start_date=None, end_date=None, service_name=None):
        """Get distributed trace statistics with optimized single query"""
        queryset = DistributedTrace.objects.all()
        
        # Apply filters
        if start_date:
            queryset = queryset.filter(start_time__gte=start_date)
        if end_date:
            queryset = queryset.filter(start_time__lte=end_date)
        if service_name:
            queryset = queryset.filter(service_name=service_name)
        
        # Use single optimized query with annotations
        stats_queryset = queryset.aggregate(
            total_traces=Count('id'),
            active_traces=Count('id', filter=Q(status='active')),
            completed_traces=Count('id', filter=Q(status='completed')),
            failed_traces=Count('id', filter=Q(status='failed'))
        )
        
        # Get duration statistics for completed traces only
        completed_traces = queryset.filter(status='completed')
        duration_stats = completed_traces.aggregate(
            avg_duration=Avg('duration_ms'),
            max_duration=Max('duration_ms')
        )
        
        # Get grouped statistics in single query
        traces_by_service = dict(
            queryset.values('service_name').annotate(count=Count('id')).values_list('service_name', 'count')
        )
        
        stats = {
            'total_traces': stats_queryset['total_traces'] or 0,
            'active_traces': stats_queryset['active_traces'] or 0,
            'completed_traces': stats_queryset['completed_traces'] or 0,
            'failed_traces': stats_queryset['failed_traces'] or 0,
            'avg_duration': duration_stats['avg_duration'] or 0,
            'max_duration': duration_stats['max_duration'] or 0,
            'traces_by_service': traces_by_service,
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
        """Get API call statistics with optimized single query"""
        queryset = APIAuditLog.objects.all()
        
        # Apply filters
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        if service_name:
            queryset = queryset.filter(service_name=service_name)
        
        # Use single optimized query with annotations
        stats_queryset = queryset.aggregate(
            total_calls=Count('id'),
            avg_response_time=Avg('response_time_ms'),
            max_response_time=Max('response_time_ms'),
            total_database_queries=Sum('database_queries'),
            avg_cache_hits=Avg('cache_hits'),
            avg_cache_misses=Avg('cache_misses')
        )
        
        # Get grouped statistics in single queries
        calls_by_method = dict(
            queryset.values('method').annotate(count=Count('id')).values_list('method', 'count')
        )
        calls_by_status = dict(
            queryset.values('status_category').annotate(count=Count('id')).values_list('status_category', 'count')
        )
        calls_by_service = dict(
            queryset.values('service_name').annotate(count=Count('id')).values_list('service_name', 'count')
        )
        
        # Calculate derived statistics
        total_calls = stats_queryset['total_calls'] or 0
        error_rate = 0
        if total_calls > 0:
            error_calls = queryset.filter(status_category='5xx').count()
            error_rate = (error_calls / total_calls) * 100
        
        cache_hit_rate = 0
        avg_hits = stats_queryset['avg_cache_hits'] or 0
        avg_misses = stats_queryset['avg_cache_misses'] or 0
        if avg_hits + avg_misses > 0:
            cache_hit_rate = (avg_hits / (avg_hits + avg_misses)) * 100
        
        stats = {
            'total_calls': total_calls,
            'calls_by_method': calls_by_method,
            'calls_by_status': calls_by_status,
            'calls_by_service': calls_by_service,
            'avg_response_time': stats_queryset['avg_response_time'] or 0,
            'max_response_time': stats_queryset['max_response_time'] or 0,
            'error_rate': error_rate,
            'total_database_queries': stats_queryset['total_database_queries'] or 0,
            'cache_hit_rate': cache_hit_rate,
        }
        
        return stats
