from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.core.exceptions import ObjectDoesNotExist
from .models import AuditLog, SecurityEvent, DataChangeLog
from .services import AuditService, SecurityEventService, DataChangeTrackingService
from django.utils.timezone import timezone, timedelta


@receiver(post_save)
def log_model_changes(sender, instance, created, **kwargs):
    """Log model changes automatically"""
    # Skip logging for audit models to prevent infinite loops
    if sender._meta.app_label == 'audit':
        return
    
    # Get the user from the request if available
    user_id = None
    request_id = None
    session_id = None
    ip_address = None
    
    # Try to get request from thread local storage
    try:
        from django.utils.deprecation import MiddlewareMixin
        from threading import local
        _thread_locals = local()
        if hasattr(_thread_locals, 'request'):
            request = _thread_locals.request
            if hasattr(request, 'user') and request.user.is_authenticated:
                user_id = request.user.id
            request_id = getattr(request, 'request_id', None)
            session_id = getattr(request, 'session_id', None)
            ip_address = getattr(request, 'ip_address', None)
    except:
        pass
    
    # Determine change type
    if created:
        change_type = 'create'
        old_values = {}
        new_values = instance.__dict__.copy()
        changed_fields = list(new_values.keys())
    else:
        change_type = 'update'
        # Get old values from the instance's _state
        old_values = getattr(instance, '_old_values', {})
        new_values = instance.__dict__.copy()
        changed_fields = list(set(new_values.keys()) - set(old_values.keys()))
    
    # Create data change log
    DataChangeTrackingService.track_data_change(
        user_id=user_id,
        service_name=sender._meta.app_label,
        change_type=change_type,
        model_name=sender._meta.model_name,
        object_id=instance.pk,
        content_type=sender._meta,
        old_values=old_values,
        new_values=new_values,
        changed_fields=changed_fields,
        request_id=request_id,
        session_id=session_id,
        ip_address=ip_address
    )


@receiver(post_delete)
def log_model_deletions(sender, instance, **kwargs):
    """Log model deletions automatically"""
    # Skip logging for audit models to prevent infinite loops
    if sender._meta.app_label == 'audit':
        return
    
    # Get the user from the request if available
    user_id = None
    request_id = None
    session_id = None
    ip_address = None
    
    try:
        from django.utils.deprecation import MiddlewareMixin
        from threading import local
        _thread_locals = local()
        if hasattr(_thread_locals, 'request'):
            request = _thread_locals.request
            if hasattr(request, 'user') and request.user.is_authenticated:
                user_id = request.user.id
            request_id = getattr(request, 'request_id', None)
            session_id = getattr(request, 'session_id', None)
            ip_address = getattr(request, 'ip_address', None)
    except:
        pass
    
    # Create data change log for deletion
    DataChangeTrackingService.track_data_change(
        user_id=user_id,
        service_name=sender._meta.app_label,
        change_type='delete',
        model_name=sender._meta.model_name,
        object_id=instance.pk,
        content_type=sender._meta,
        old_values=instance.__dict__.copy(),
        new_values={},
        changed_fields=['deleted'],
        request_id=request_id,
        session_id=session_id,
        ip_address=ip_address
    )


@receiver(pre_save)
def store_old_values(sender, instance, **kwargs):
    """Store old values before saving for comparison"""
    # Skip for audit models
    if sender._meta.app_label == 'audit':
        return
    
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_values = old_instance.__dict__.copy()
        except ObjectDoesNotExist:
            instance._old_values = {}


@receiver(user_logged_in)
def log_user_login(sender, user, request, **kwargs):
    """Log successful user login"""
    SecurityEventService.create_security_event(
        event_type='login',
        severity='low',
        user_id=user.id,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        session_id=request.session.session_key,
        description=f'User {user.username} logged in successfully',
        risk_score=0
    )


@receiver(user_logged_out)
def log_user_logout(sender, user, request, **kwargs):
    """Log user logout"""
    SecurityEventService.create_security_event(
        event_type='logout',
        severity='low',
        user_id=user.id if user else None,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        session_id=request.session.session_key,
        description=f'User {user.username if user else "Unknown"} logged out',
        risk_score=0
    )


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    """Log failed login attempts"""
    username = credentials.get('username', 'unknown')
    ip_address = request.META.get('REMOTE_ADDR')
    
    # Calculate risk score based on failed attempts
    risk_score = 30  # Base risk score for failed login
    
    # Check for multiple failed attempts from same IP
    recent_failures = SecurityEvent.objects.filter(
        event_type='failed_login',
        ip_address=ip_address,
        timestamp__gte=timezone.now() - timedelta(minutes=15)
    ).count()
    
    if recent_failures > 5:
        risk_score = 80
    elif recent_failures > 2:
        risk_score = 50
    
    SecurityEventService.create_security_event(
        event_type='failed_login',
        severity='medium' if risk_score > 50 else 'low',
        user_id=None,
        ip_address=ip_address,
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        session_id=request.session.session_key,
        description=f'Failed login attempt for username: {username}',
        risk_score=risk_score,
        risk_factors=['multiple_failed_attempts'] if recent_failures > 2 else []
    )


# Middleware to capture request context
class AuditMiddleware:
    """Middleware to capture request context for audit logging"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Generate request ID
        import uuid
        request.request_id = str(uuid.uuid4())
        
        # Capture IP address
        request.ip_address = self.get_client_ip(request)
        
        # Capture session ID
        if hasattr(request, 'session'):
            request.session_id = request.session.session_key
        
        # Store request in thread locals for signal handlers
        from threading import local
        _thread_locals = local()
        _thread_locals.request = request
        
        response = self.get_response(request)
        
        # Log API call if it's an API endpoint
        if request.path.startswith('/api/'):
            self.log_api_call(request, response)
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def log_api_call(self, request, response):
        """Log API call details"""
        from .services import APIAuditService
        
        # Calculate response time
        import time
        start_time = getattr(request, '_start_time', time.time())
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Get user ID
        user_id = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = request.user.id
        
        # Log the API call
        APIAuditService.log_api_call(
            service_name=request.path.split('/')[2] if len(request.path.split('/')) > 2 else 'unknown',
            endpoint=request.path,
            method=request.method,
            user_id=user_id,
            session_id=getattr(request, 'session_id', None),
            request_id=getattr(request, 'request_id', None),
            ip_address=getattr(request, 'ip_address', None),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            referer=request.META.get('HTTP_REFERER', ''),
            request_headers=dict(request.headers),
            request_params=dict(request.GET),
            request_body=request.body.decode('utf-8') if request.body else '',
            request_size=len(request.body) if request.body else 0,
            response_status=response.status_code,
            response_time_ms=response_time_ms,
            response_size=len(response.content) if hasattr(response, 'content') else 0,
            response_body=response.content.decode('utf-8') if hasattr(response, 'content') else '',
            error_type=None if response.status_code < 400 else 'HTTP_ERROR',
            error_message=None if response.status_code < 400 else f'HTTP {response.status_code}',
            database_queries=0,  # TODO: Implement query counting
            cache_hits=0,  # TODO: Implement cache hit counting
            cache_misses=0,  # TODO: Implement cache miss counting
            metadata={'user_agent': request.META.get('HTTP_USER_AGENT', '')}
        )
