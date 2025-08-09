import time
import uuid
import logging
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse
from django.urls import resolve
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import json
import redis
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

logger = logging.getLogger(__name__)

# Initialize tracing
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Jaeger exporter
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=14268,
)

span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Auto-instrument Django, requests, and psycopg2
DjangoInstrumentor().instrument()
RequestsInstrumentor().instrument()
Psycopg2Instrumentor().instrument()

# Prometheus metrics
REQUEST_COUNT = Counter(
    'django_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code', 'service']
)

REQUEST_DURATION = Histogram(
    'django_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint', 'service']
)

ACTIVE_REQUESTS = Gauge(
    'django_http_requests_active',
    'Active HTTP requests',
    ['service']
)

BUSINESS_METRICS = {
    'orders_total': Counter('orders_total', 'Total orders'),
    'orders_failed': Counter('orders_failed_total', 'Failed orders'),
    'payments_total': Counter('payments_total', 'Total payments'),
    'payments_failed': Counter('payments_failed_total', 'Failed payments'),
    'inventory_items': Gauge('inventory_items_quantity', 'Inventory quantity', ['product_id']),
    'user_registrations': Counter('user_registrations_total', 'Total user registrations'),
    'user_logins': Counter('user_logins_total', 'Total user logins'),
}

# Circuit breaker metrics
CIRCUIT_BREAKER_STATE = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['service', 'state']
)

# Database metrics
DB_CONNECTIONS = Gauge('django_db_connections_used', 'Used database connections')
DB_CONNECTIONS_MAX = Gauge('django_db_connections_max', 'Maximum database connections')

# Cache metrics
CACHE_HITS = Counter('django_cache_hits_total', 'Cache hits')
CACHE_MISSES = Counter('django_cache_misses_total', 'Cache misses')


class PrometheusMetricsMiddleware:
    """Middleware for collecting Prometheus metrics"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        
    def __call__(self, request):
        # Skip metrics collection for the metrics endpoint itself
        if request.path == '/prometheus/metrics':
            return self.get_response(request)
            
        service_name = self._get_service_name(request)
        ACTIVE_REQUESTS.labels(service=service_name).inc()
        
        start_time = time.time()
        
        response = self.get_response(request)
        
        duration = time.time() - start_time
        
        # Get endpoint name
        try:
            endpoint = resolve(request.path_info).url_name or request.path_info
        except:
            endpoint = request.path_info
            
        # Record metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status_code=response.status_code,
            service=service_name
        ).inc()
        
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=endpoint,
            service=service_name
        ).observe(duration)
        
        ACTIVE_REQUESTS.labels(service=service_name).dec()
        
        return response
    
    def _get_service_name(self, request):
        """Extract service name from request path"""
        path_parts = request.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[0] == 'api':
            return path_parts[1]
        return 'gateway'


class DistributedTracingMiddleware:
    """Middleware for distributed tracing"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Create or extract trace context
        trace_id = request.META.get('HTTP_X_TRACE_ID') or str(uuid.uuid4())
        request.trace_id = trace_id
        
        with tracer.start_as_current_span(
            f"{request.method} {request.path}",
            attributes={
                "http.method": request.method,
                "http.url": request.build_absolute_uri(),
                "http.user_agent": request.META.get('HTTP_USER_AGENT', ''),
                "trace.id": trace_id,
            }
        ) as span:
            try:
                response = self.get_response(request)
                
                span.set_attribute("http.status_code", response.status_code)
                if response.status_code >= 400:
                    span.set_status(trace.Status(trace.StatusCode.ERROR))
                
                # Add trace ID to response headers
                response['X-Trace-ID'] = trace_id
                
                return response
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise


class BusinessMetricsMiddleware:
    """Middleware for collecting business metrics"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        response = self.get_response(request)
        
        # Track business events based on endpoints
        self._track_business_events(request, response)
        
        return response
    
    def _track_business_events(self, request, response):
        """Track business-specific events"""
        try:
            if response.status_code < 400:  # Only track successful requests
                
                # Order events
                if 'orders' in request.path:
                    if request.method == 'POST':
                        BUSINESS_METRICS['orders_total'].inc()
                        
                # Payment events
                elif 'payments' in request.path:
                    if request.method == 'POST':
                        BUSINESS_METRICS['payments_total'].inc()
                        
                # User registration
                elif 'auth/register' in request.path and request.method == 'POST':
                    BUSINESS_METRICS['user_registrations'].inc()
                    
                # User login
                elif 'auth/login' in request.path and request.method == 'POST':
                    BUSINESS_METRICS['user_logins'].inc()
                    
            else:  # Track failures
                if 'orders' in request.path and request.method == 'POST':
                    BUSINESS_METRICS['orders_failed'].inc()
                elif 'payments' in request.path and request.method == 'POST':
                    BUSINESS_METRICS['payments_failed'].inc()
                    
        except Exception as e:
            logger.error(f"Error tracking business metrics: {e}")


class PerformanceMonitoringMiddleware:
    """Middleware for performance monitoring"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        
    def __call__(self, request):
        start_time = time.time()
        start_memory = self._get_memory_usage()
        
        response = self.get_response(request)
        
        end_time = time.time()
        end_memory = self._get_memory_usage()
        
        # Log performance data
        perf_data = {
            'timestamp': timezone.now().isoformat(),
            'path': request.path,
            'method': request.method,
            'duration_ms': round((end_time - start_time) * 1000, 2),
            'memory_delta_mb': round((end_memory - start_memory) / 1024 / 1024, 2),
            'status_code': response.status_code,
            'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
        }
        
        # Store in Redis for real-time monitoring
        self.redis_client.lpush('performance_logs', json.dumps(perf_data))
        self.redis_client.ltrim('performance_logs', 0, 1000)  # Keep last 1000 entries
        
        return response
    
    def _get_memory_usage(self):
        """Get current memory usage"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            return 0


def prometheus_metrics_view(request):
    """Endpoint for Prometheus metrics scraping"""
    metrics_data = generate_latest()
    return HttpResponse(metrics_data, content_type=CONTENT_TYPE_LATEST)


# Custom metric collection functions
def update_inventory_metrics():
    """Update inventory metrics from database"""
    try:
        from inventory.models import InventoryItem
        
        for item in InventoryItem.objects.all():
            BUSINESS_METRICS['inventory_items'].labels(
                product_id=str(item.product_id)
            ).set(item.quantity_available)
            
    except Exception as e:
        logger.error(f"Error updating inventory metrics: {e}")


def update_circuit_breaker_metrics():
    """Update circuit breaker metrics from Redis"""
    try:
        redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        keys = redis_client.keys('circuit_breaker:*')
        
        for key in keys:
            service_name = key.decode().split(':')[1]
            state_data = redis_client.get(key)
            
            if state_data:
                data = json.loads(state_data)
                state = data.get('state', 'CLOSED')
                
                # Convert state to numeric value
                state_value = {'CLOSED': 0, 'OPEN': 1, 'HALF_OPEN': 2}.get(state, 0)
                
                CIRCUIT_BREAKER_STATE.labels(
                    service=service_name,
                    state=state
                ).set(state_value)
                
    except Exception as e:
        logger.error(f"Error updating circuit breaker metrics: {e}")


def update_database_metrics():
    """Update database connection metrics"""
    try:
        from django.db import connection
        
        # Get database connection info
        queries_count = len(connection.queries)
        
        # This is a simplified example - in production you'd use proper connection pool metrics
        DB_CONNECTIONS.set(1 if connection.connection else 0)
        DB_CONNECTIONS_MAX.set(1)  # This should come from your connection pool settings
        
    except Exception as e:
        logger.error(f"Error updating database metrics: {e}")


# Logging configuration for structured logging
class StructuredLoggingFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add extra fields if available
        if hasattr(record, 'trace_id'):
            log_entry['trace_id'] = record.trace_id
            
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
            
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry)


# Health check with metrics
def health_check_with_metrics():
    """Enhanced health check that includes metrics"""
    health_data = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'checks': {}
    }
    
    # Check database
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_data['checks']['database'] = 'healthy'
    except Exception as e:
        health_data['checks']['database'] = f'unhealthy: {str(e)}'
        health_data['status'] = 'unhealthy'
    
    # Check Redis
    try:
        redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        redis_client.ping()
        health_data['checks']['redis'] = 'healthy'
    except Exception as e:
        health_data['checks']['redis'] = f'unhealthy: {str(e)}'
        health_data['status'] = 'unhealthy'
    
    # Add performance metrics
    try:
        import psutil
        health_data['metrics'] = {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent
        }
    except ImportError:
        pass
    
    return health_data
