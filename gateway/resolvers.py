import requests
import logging
from functools import cache
from django.conf import settings
from .middleware import (
    ServiceDiscoveryClient, 
    circuit_breaker,
    CircuitBreakerOpenException,
    ServiceUnavailableException,
    RetryMiddleware
)

logger = logging.getLogger(__name__)

# Initialize components
service_client = ServiceDiscoveryClient()
retry_middleware = RetryMiddleware()

@circuit_breaker(failure_threshold=5, recovery_timeout=60)
@cache
def resolve_products(obj, info):
    """Resolve products from the products service with circuit breaker"""
    try:
        def make_call():
            return service_client.call_service('products-service', '/api/products/', timeout=10)
        
        response = retry_middleware.retry_call(make_call)
        return response.json()
    except (CircuitBreakerOpenException, ServiceUnavailableException) as e:
        logger.warning(f"Products service unavailable: {e}")
        return []
    except Exception as e:
        logger.error(f"Error resolving products: {e}")
        return []

@circuit_breaker(failure_threshold=5, recovery_timeout=60)
@cache
def resolve_orders(obj, info):
    """Resolve orders from the orders service with circuit breaker"""
    try:
        def make_call():
            return service_client.call_service('orders-service', '/api/orders/', timeout=10)
        
        response = retry_middleware.retry_call(make_call)
        return response.json()
    except (CircuitBreakerOpenException, ServiceUnavailableException) as e:
        logger.warning(f"Orders service unavailable: {e}")
        return []
    except Exception as e:
        logger.error(f"Error resolving orders: {e}")
        return []

@circuit_breaker(failure_threshold=5, recovery_timeout=60)
@cache
def resolve_inventory(obj, info):
    """Resolve inventory from the inventory service with circuit breaker"""
    try:
        def make_call():
            return service_client.call_service('inventory-service', '/api/inventory/', timeout=10)
        
        response = retry_middleware.retry_call(make_call)
        return response.json()
    except (CircuitBreakerOpenException, ServiceUnavailableException) as e:
        logger.warning(f"Inventory service unavailable: {e}")
        return []
    except Exception as e:
        logger.error(f"Error resolving inventory: {e}")
        return []

@circuit_breaker(failure_threshold=5, recovery_timeout=60)
@cache
def resolve_payments(obj, info):
    """Resolve payments from the payments service with circuit breaker"""
    try:
        def make_call():
            return service_client.call_service('payments-service', '/api/payments/', timeout=10)
        
        response = retry_middleware.retry_call(make_call)
        return response.json()
    except (CircuitBreakerOpenException, ServiceUnavailableException) as e:
        logger.warning(f"Payments service unavailable: {e}")
        return []
    except Exception as e:
        logger.error(f"Error resolving payments: {e}")
        return []

@circuit_breaker(failure_threshold=3, recovery_timeout=30)
@cache
def resolve_notifications(obj, info):
    """Resolve notifications from the notification service with circuit breaker"""
    try:
        def make_call():
            return service_client.call_service('notification-service', '/api/notification/', timeout=5)
        
        response = retry_middleware.retry_call(make_call)
        return response.json()
    except (CircuitBreakerOpenException, ServiceUnavailableException) as e:
        logger.warning(f"Notification service unavailable: {e}")
        return []
    except Exception as e:
        logger.error(f"Error resolving notifications: {e}")
        return []
