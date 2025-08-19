import time
import json
import redis
import requests
from functools import wraps
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
import logging
import random
from typing import Dict, List, Optional
from threading import Lock
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class RateLimitingMiddleware:
    """Rate limiting middleware for API Gateway"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        
    def __call__(self, request):
        # Skip rate limiting for health checks and admin
        if request.path.startswith(('/health/', '/admin/')):
            return self.get_response(request)
        
        # Get client identifier
        client_id = self.get_client_identifier(request)
        
        # Check rate limit
        if not self.check_rate_limit(client_id, request):
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'message': 'Too many requests. Please try again later.',
                'retry_after': 60
            }, status=429)
        
        response = self.get_response(request)
        
        # Add rate limit headers
        self.add_rate_limit_headers(response, client_id)
        
        return response
    
    def get_client_identifier(self, request):
        """Get unique client identifier for rate limiting"""
        # Try to get user ID first
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        # Fall back to IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        return f"ip:{ip}"
    
    def check_rate_limit(self, client_id, request):
        """Check if client has exceeded rate limit"""
        # Different limits for different endpoints
        limits = self.get_rate_limits(request.path)
        
        for window, limit in limits.items():
            key = f"rate_limit:{client_id}:{window}"
            current = self.redis_client.get(key)
            
            if current is None:
                # First request in window
                self.redis_client.setex(key, window, 1)
            else:
                current = int(current)
                if current >= limit:
                    return False
                # Increment counter
                self.redis_client.incr(key)
        
        return True
    
    def get_rate_limits(self, path):
        """Get rate limits based on endpoint"""
        # Default limits (window_seconds: max_requests)
        default_limits = {60: 100, 3600: 1000}  # 100/min, 1000/hour
        
        # Stricter limits for auth endpoints
        if path.startswith('/api/auth/'):
            return {60: 20, 3600: 100}  # 20/min, 100/hour
        
        # Looser limits for read-only endpoints
        if any(path.startswith(p) for p in ['/api/products/', '/api/inventory/']) and 'GET' in path:
            return {60: 200, 3600: 2000}  # 200/min, 2000/hour
        
        return default_limits
    
    def add_rate_limit_headers(self, response, client_id):
        """Add rate limit headers to response"""
        try:
            key = f"rate_limit:{client_id}:60"
            current = self.redis_client.get(key)
            if current:
                response['X-RateLimit-Limit'] = '100'
                response['X-RateLimit-Remaining'] = str(max(0, 100 - int(current)))
                response['X-RateLimit-Reset'] = str(int(time.time()) + 60)
        except Exception as e:
            logger.error(f"Error adding rate limit headers: {e}")


class CircuitBreakerMiddleware:
    """Circuit breaker middleware for service calls"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.circuit_breakers = {}
        self.lock = Lock()
        
    def __call__(self, request):
        return self.get_response(request)
    
    def get_circuit_breaker(self, service_name):
        """Get or create circuit breaker for service"""
        if service_name not in self.circuit_breakers:
            with self.lock:
                if service_name not in self.circuit_breakers:
                    self.circuit_breakers[service_name] = CircuitBreaker(service_name)
        return self.circuit_breakers[service_name]


class CircuitBreaker:
    """Circuit breaker implementation"""
    
    def __init__(self, name, failure_threshold=5, recovery_timeout=60, expected_exception=Exception):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.lock = Lock()
        
        # Redis for distributed circuit breaker state
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        with self.lock:
            # Check distributed state
            self._sync_state()
            
            if self.state == 'OPEN':
                if self._should_attempt_reset():
                    self.state = 'HALF_OPEN'
                    logger.info(f"Circuit breaker {self.name} moving to HALF_OPEN")
                else:
                    raise CircuitBreakerOpenException(f"Circuit breaker {self.name} is OPEN")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
            logger.info(f"Circuit breaker {self.name} reset to CLOSED")
        self._update_distributed_state()
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"Circuit breaker {self.name} opened after {self.failure_count} failures")
        
        self._update_distributed_state()
    
    def _should_attempt_reset(self):
        """Check if circuit breaker should attempt reset"""
        return (self.last_failure_time and 
                datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout))
    
    def _sync_state(self):
        """Sync state with distributed cache"""
        try:
            key = f"circuit_breaker:{self.name}"
            state_data = self.redis_client.get(key)
            if state_data:
                data = json.loads(state_data)
                self.state = data.get('state', 'CLOSED')
                self.failure_count = data.get('failure_count', 0)
                last_failure = data.get('last_failure_time')
                if last_failure:
                    self.last_failure_time = datetime.fromisoformat(last_failure)
        except Exception as e:
            logger.error(f"Error syncing circuit breaker state: {e}")
    
    def _update_distributed_state(self):
        """Update distributed state"""
        try:
            key = f"circuit_breaker:{self.name}"
            data = {
                'state': self.state,
                'failure_count': self.failure_count,
                'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None
            }
            self.redis_client.setex(key, 300, json.dumps(data))  
        except Exception as e:
            logger.error(f"Error updating circuit breaker state: {e}")


class LoadBalancerMiddleware:
    """Load balancer middleware for service discovery"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.service_instances = {}
        self.last_discovery_time = {}
        self.discovery_interval = 30 
        
    def __call__(self, request):
        return self.get_response(request)
    
    def get_service_instance(self, service_name, algorithm='round_robin'):
        """Get service instance using load balancing algorithm"""
        instances = self._get_healthy_instances(service_name)
        
        if not instances:
            raise ServiceUnavailableException(f"No healthy instances for service {service_name}")
        
        if algorithm == 'round_robin':
            return self._round_robin_select(service_name, instances)
        elif algorithm == 'weighted_round_robin':
            return self._weighted_round_robin_select(service_name, instances)
        elif algorithm == 'least_connections':
            return self._least_connections_select(service_name, instances)
        elif algorithm == 'random':
            return random.choice(instances)
        else:
            return instances[0]  
    
    def _get_healthy_instances(self, service_name):
        """Get healthy service instances from service discovery"""
        # Check if we need to refresh service discovery
        now = time.time()
        if (service_name not in self.last_discovery_time or 
            now - self.last_discovery_time[service_name] > self.discovery_interval):
            
            self._discover_services(service_name)
            self.last_discovery_time[service_name] = now
        
        return self.service_instances.get(service_name, [])
    
    def _discover_services(self, service_name):
        """Discover service instances from service registry"""
        try:
            from service_discovery.services import ServiceRegistryService
            
            registry_service = ServiceRegistryService()
            instances = registry_service.get_service_instances(service_name, healthy_only=True)
            
            self.service_instances[service_name] = [
                {
                    'id': instance.instance_id,
                    'host': instance.host,
                    'port': instance.port,
                    'protocol': instance.protocol,
                    'weight': instance.load_balancer_weight,
                    'connections': 0  
                }
                for instance in instances
            ]
            
        except Exception as e:
            logger.error(f"Error discovering services for {service_name}: {e}")
            # Keep existing instances if discovery fails
    
    def _round_robin_select(self, service_name, instances):
        """Round robin load balancing"""
        key = f"round_robin:{service_name}"
        index = cache.get(key, 0)
        selected = instances[index % len(instances)]
        cache.set(key, (index + 1) % len(instances), 300)
        return selected
    
    def _weighted_round_robin_select(self, service_name, instances):
        """Weighted round robin load balancing"""
        total_weight = sum(instance['weight'] for instance in instances)
        random_weight = random.randint(1, total_weight)
        
        current_weight = 0
        for instance in instances:
            current_weight += instance['weight']
            if random_weight <= current_weight:
                return instance
        
        return instances[0]  
    
    def _least_connections_select(self, service_name, instances):
        """Least connections load balancing"""
        return min(instances, key=lambda x: x['connections'])


class ServiceDiscoveryClient:
    """Client for service discovery integration"""
    
    def __init__(self):
        self.circuit_breaker_middleware = CircuitBreakerMiddleware(None)
        self.load_balancer = LoadBalancerMiddleware(None)
        self.session = requests.Session()
        
    def call_service(self, service_name, path, method='GET', data=None, headers=None, timeout=30):
        """Make a call to a service with circuit breaker and load balancing"""
        circuit_breaker = self.circuit_breaker_middleware.get_circuit_breaker(service_name)
        
        def make_request():
            instance = self.load_balancer.get_service_instance(service_name)
            url = f"{instance['protocol']}://{instance['host']}:{instance['port']}{path}"
            
            # Track connection
            instance['connections'] += 1
            
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    headers=headers,
                    timeout=timeout
                )
                response.raise_for_status()
                return response
            finally:
                instance['connections'] -= 1
        
        return circuit_breaker.call(make_request)


class RetryMiddleware:
    """Retry middleware with exponential backoff"""
    
    def __init__(self, max_retries=3, base_delay=1, max_delay=60, backoff_factor=2):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
    
    def retry_call(self, func, *args, **kwargs):
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (requests.exceptions.RequestException, ServiceUnavailableException) as e:
                last_exception = e
                
                if attempt == self.max_retries:
                    break
                
                delay = min(self.base_delay * (self.backoff_factor ** attempt), self.max_delay)
                # Add jitter
                delay *= (0.5 + random.random() * 0.5)
                
                logger.warning(f"Retry attempt {attempt + 1} after {delay:.2f}s delay: {e}")
                time.sleep(delay)
        
        raise last_exception


# Custom Exceptions
class CircuitBreakerOpenException(Exception):
    """Raised when circuit breaker is open"""
    pass


class ServiceUnavailableException(Exception):
    """Raised when service is unavailable"""
    pass


# Rate limiting decorator
def rate_limit(requests_per_minute=60, per_user=True):
    """Rate limiting decorator"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get identifier
            if per_user and hasattr(request, 'user') and request.user.is_authenticated:
                identifier = f"user:{request.user.id}"
            else:
                identifier = f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"
            
            # Check rate limit
            key = f"rate_limit:{identifier}:{view_func.__name__}"
            redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            
            current = redis_client.get(key)
            if current is None:
                redis_client.setex(key, 60, 1)
            else:
                current = int(current)
                if current >= requests_per_minute:
                    return JsonResponse({
                        'error': 'Rate limit exceeded',
                        'message': f'Maximum {requests_per_minute} requests per minute'
                    }, status=429)
                redis_client.incr(key)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Circuit breaker decorator
def circuit_breaker(failure_threshold=5, recovery_timeout=60):
    """Circuit breaker decorator"""
    def decorator(func):
        breaker = CircuitBreaker(
            name=func.__name__,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator
