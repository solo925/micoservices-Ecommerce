import time
import random
import threading
import asyncio
from functools import wraps
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import redis
import json
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: int = 60
    expected_exception: type = Exception


@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True


@dataclass
class BulkheadConfig:
    max_concurrent_calls: int = 10
    max_wait_duration: int = 30


class AdvancedCircuitBreaker:
    """Advanced Circuit Breaker with sliding window and distributed state"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.now()
        self.lock = threading.Lock()
        
        # Sliding window for better failure detection
        self.call_history = []
        self.window_size = 100
        
        # Redis for distributed state
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        with self.lock:
            self._sync_distributed_state()
            
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    self._record_call(False, datetime.now())
                    raise CircuitBreakerOpenException(f"Circuit breaker {self.name} is OPEN")
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
                elif self.failure_count > 0:
                    self._transition_to_open()
                    raise CircuitBreakerOpenException(f"Circuit breaker {self.name} failed in HALF_OPEN state")
        
        start_time = time.time()
        call_timestamp = datetime.now()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            self._on_success(call_timestamp, duration)
            return result
            
        except self.config.expected_exception as e:
            duration = time.time() - start_time
            self._on_failure(call_timestamp, duration, str(e))
            raise e
    
    def _on_success(self, timestamp: datetime, duration: float):
        """Handle successful call"""
        with self.lock:
            self._record_call(True, timestamp, duration)
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            elif self.state == CircuitBreakerState.CLOSED:
                self.failure_count = max(0, self.failure_count - 1)
    
    def _on_failure(self, timestamp: datetime, duration: float, error: str):
        """Handle failed call"""
        with self.lock:
            self._record_call(False, timestamp, duration, error)
            self.failure_count += 1
            self.last_failure_time = timestamp
            
            if self.state == CircuitBreakerState.CLOSED:
                if self._should_trip():
                    self._transition_to_open()
            elif self.state == CircuitBreakerState.HALF_OPEN:
                self._transition_to_open()
    
    def _should_trip(self) -> bool:
        """Determine if circuit breaker should trip based on sliding window"""
        if len(self.call_history) < self.config.failure_threshold:
            return False
        
        recent_calls = self.call_history[-self.window_size:]
        failure_rate = sum(1 for call in recent_calls if not call['success']) / len(recent_calls)
        
        return failure_rate >= 0.5 and self.failure_count >= self.config.failure_threshold
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if not self.last_failure_time:
            return True
        
        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.timeout
    
    def _transition_to_open(self):
        """Transition to OPEN state"""
        self.state = CircuitBreakerState.OPEN
        self.last_state_change = datetime.now()
        self.success_count = 0
        self._update_distributed_state()
        logger.warning(f"Circuit breaker {self.name} transitioned to OPEN")
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state"""
        self.state = CircuitBreakerState.HALF_OPEN
        self.last_state_change = datetime.now()
        self.failure_count = 0
        self.success_count = 0
        self._update_distributed_state()
        logger.info(f"Circuit breaker {self.name} transitioned to HALF_OPEN")
    
    def _transition_to_closed(self):
        """Transition to CLOSED state"""
        self.state = CircuitBreakerState.CLOSED
        self.last_state_change = datetime.now()
        self.failure_count = 0
        self.success_count = 0
        self._update_distributed_state()
        logger.info(f"Circuit breaker {self.name} transitioned to CLOSED")
    
    def _record_call(self, success: bool, timestamp: datetime, duration: float = 0, error: str = None):
        """Record call in sliding window"""
        call_record = {
            'success': success,
            'timestamp': timestamp.isoformat(),
            'duration': duration,
            'error': error
        }
        
        self.call_history.append(call_record)
        
        # Keep only recent calls
        if len(self.call_history) > self.window_size:
            self.call_history = self.call_history[-self.window_size:]
    
    def _sync_distributed_state(self):
        """Sync state with distributed cache"""
        try:
            key = f"circuit_breaker:{self.name}"
            state_data = self.redis_client.get(key)
            
            if state_data:
                data = json.loads(state_data)
                remote_state = CircuitBreakerState(data.get('state', 'closed'))
                remote_change_time = datetime.fromisoformat(data.get('last_state_change'))
                
                # Use most recent state change
                if remote_change_time > self.last_state_change:
                    self.state = remote_state
                    self.failure_count = data.get('failure_count', 0)
                    self.success_count = data.get('success_count', 0)
                    self.last_state_change = remote_change_time
                    
                    if data.get('last_failure_time'):
                        self.last_failure_time = datetime.fromisoformat(data['last_failure_time'])
                        
        except Exception as e:
            logger.error(f"Error syncing circuit breaker state: {e}")
    
    def _update_distributed_state(self):
        """Update distributed state"""
        try:
            key = f"circuit_breaker:{self.name}"
            data = {
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'last_state_change': self.last_state_change.isoformat(),
                'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None
            }
            
            self.redis_client.setex(key, 300, json.dumps(data))
            
        except Exception as e:
            logger.error(f"Error updating circuit breaker state: {e}")
    
    def get_metrics(self) -> Dict:
        """Get circuit breaker metrics"""
        with self.lock:
            recent_calls = self.call_history[-self.window_size:] if self.call_history else []
            success_rate = sum(1 for call in recent_calls if call['success']) / len(recent_calls) if recent_calls else 1.0
            
            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'success_rate': success_rate,
                'total_calls': len(recent_calls),
                'last_state_change': self.last_state_change.isoformat(),
                'configuration': {
                    'failure_threshold': self.config.failure_threshold,
                    'success_threshold': self.config.success_threshold,
                    'timeout': self.config.timeout
                }
            }


class RetryMechanism:
    """Advanced retry mechanism with exponential backoff and jitter"""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                if attempt == self.config.max_attempts - 1:
                    logger.error(f"All retry attempts failed for {func.__name__}: {e}")
                    break
                
                delay = self._calculate_delay(attempt)
                logger.warning(f"Retry attempt {attempt + 1} for {func.__name__} after {delay:.2f}s: {e}")
                time.sleep(delay)
        
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter"""
        delay = min(
            self.config.base_delay * (self.config.backoff_factor ** attempt),
            self.config.max_delay
        )
        
        if self.config.jitter:
            # Add random jitter (±25%)
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


class Bulkhead:
    """Bulkhead pattern implementation for resource isolation"""
    
    def __init__(self, name: str, config: BulkheadConfig = None):
        self.name = name
        self.config = config or BulkheadConfig()
        self.semaphore = threading.Semaphore(self.config.max_concurrent_calls)
        self.active_calls = 0
        self.total_calls = 0
        self.rejected_calls = 0
        self.lock = threading.Lock()
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with bulkhead protection"""
        acquired = self.semaphore.acquire(timeout=self.config.max_wait_duration)
        
        if not acquired:
            with self.lock:
                self.rejected_calls += 1
            raise BulkheadException(f"Bulkhead {self.name} capacity exceeded")
        
        try:
            with self.lock:
                self.active_calls += 1
                self.total_calls += 1
            
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            logger.debug(f"Bulkhead {self.name} call completed in {duration:.2f}s")
            return result
            
        finally:
            with self.lock:
                self.active_calls -= 1
            self.semaphore.release()
    
    def get_metrics(self) -> Dict:
        """Get bulkhead metrics"""
        with self.lock:
            return {
                'name': self.name,
                'active_calls': self.active_calls,
                'total_calls': self.total_calls,
                'rejected_calls': self.rejected_calls,
                'available_permits': self.semaphore._value,
                'max_concurrent_calls': self.config.max_concurrent_calls,
                'rejection_rate': self.rejected_calls / max(self.total_calls, 1)
            }


class TimeoutHandler:
    """Timeout handler with configurable timeouts"""
    
    def __init__(self, timeout: float):
        self.timeout = timeout
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with timeout"""
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutException(f"Function {func.__name__} timed out after {self.timeout}s")
        
        # Set up timeout
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(self.timeout))
        
        try:
            result = func(*args, **kwargs)
            signal.alarm(0)  # Cancel timeout
            return result
        finally:
            signal.signal(signal.SIGALRM, old_handler)


class ResilientServiceCaller:
    """Combines all resilience patterns for service calls"""
    
    def __init__(self, service_name: str, 
                 circuit_breaker_config: CircuitBreakerConfig = None,
                 retry_config: RetryConfig = None,
                 bulkhead_config: BulkheadConfig = None,
                 timeout: float = 30.0):
        
        self.service_name = service_name
        self.circuit_breaker = AdvancedCircuitBreaker(service_name, circuit_breaker_config)
        self.retry = RetryMechanism(retry_config)
        self.bulkhead = Bulkhead(service_name, bulkhead_config)
        self.timeout_handler = TimeoutHandler(timeout)
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with all resilience patterns"""
        def resilient_call():
            def bulkhead_call():
                def timeout_call():
                    return self.timeout_handler.execute(func, *args, **kwargs)
                return self.bulkhead.execute(timeout_call)
            return self.circuit_breaker.call(bulkhead_call)
        
        return self.retry.execute(resilient_call)
    
    def get_metrics(self) -> Dict:
        """Get all metrics"""
        return {
            'service_name': self.service_name,
            'circuit_breaker': self.circuit_breaker.get_metrics(),
            'bulkhead': self.bulkhead.get_metrics()
        }


# Chaos Engineering Components
class ChaosEngineeringEngine:
    """Chaos engineering for testing system resilience"""
    
    def __init__(self):
        self.active_experiments = {}
        self.experiment_history = []
    
    def inject_latency(self, service_name: str, latency_ms: int, probability: float = 0.1):
        """Inject artificial latency"""
        def latency_injector(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if random.random() < probability:
                    delay = latency_ms / 1000.0
                    logger.warning(f"Chaos: Injecting {latency_ms}ms latency to {service_name}")
                    time.sleep(delay)
                return func(*args, **kwargs)
            return wrapper
        return latency_injector
    
    def inject_failures(self, service_name: str, failure_rate: float = 0.1, 
                       exception_type: type = Exception, error_message: str = "Chaos failure"):
        """Inject artificial failures"""
        def failure_injector(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if random.random() < failure_rate:
                    logger.warning(f"Chaos: Injecting failure to {service_name}")
                    raise exception_type(error_message)
                return func(*args, **kwargs)
            return wrapper
        return failure_injector
    
    def inject_resource_exhaustion(self, service_name: str, probability: float = 0.05):
        """Simulate resource exhaustion"""
        def resource_exhaustion_injector(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if random.random() < probability:
                    logger.warning(f"Chaos: Simulating resource exhaustion for {service_name}")
                    # Simulate CPU spike
                    end_time = time.time() + 0.1  # 100ms CPU spike
                    while time.time() < end_time:
                        pass
                return func(*args, **kwargs)
            return wrapper
        return resource_exhaustion_injector
    
    def start_experiment(self, experiment_name: str, experiment_func: Callable, duration: int):
        """Start a chaos experiment"""
        experiment = {
            'name': experiment_name,
            'start_time': datetime.now(),
            'duration': duration,
            'status': 'running'
        }
        
        self.active_experiments[experiment_name] = experiment
        
        # Schedule experiment end
        def end_experiment():
            time.sleep(duration)
            if experiment_name in self.active_experiments:
                experiment['end_time'] = datetime.now()
                experiment['status'] = 'completed'
                self.experiment_history.append(experiment)
                del self.active_experiments[experiment_name]
                logger.info(f"Chaos experiment {experiment_name} completed")
        
        threading.Thread(target=end_experiment, daemon=True).start()
        logger.info(f"Started chaos experiment: {experiment_name}")
    
    def get_experiment_status(self) -> Dict:
        """Get status of all experiments"""
        return {
            'active_experiments': self.active_experiments,
            'experiment_history': self.experiment_history[-10:]  # Last 10 experiments
        }


# Custom Exceptions
class CircuitBreakerOpenException(Exception):
    """Raised when circuit breaker is open"""
    pass


class BulkheadException(Exception):
    """Raised when bulkhead capacity is exceeded"""
    pass


class TimeoutException(Exception):
    """Raised when operation times out"""
    pass


# Decorators for easy use
def circuit_breaker(name: str, failure_threshold: int = 5, timeout: int = 60):
    """Circuit breaker decorator"""
    def decorator(func):
        breaker = AdvancedCircuitBreaker(name, CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            timeout=timeout
        ))
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


def retry(max_attempts: int = 3, base_delay: float = 1.0, backoff_factor: float = 2.0):
    """Retry decorator"""
    def decorator(func):
        retry_mechanism = RetryMechanism(RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            backoff_factor=backoff_factor
        ))
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return retry_mechanism.execute(func, *args, **kwargs)
        return wrapper
    return decorator


def bulkhead(name: str, max_concurrent_calls: int = 10):
    """Bulkhead decorator"""
    def decorator(func):
        bulkhead_instance = Bulkhead(name, BulkheadConfig(
            max_concurrent_calls=max_concurrent_calls
        ))
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return bulkhead_instance.execute(func, *args, **kwargs)
        return wrapper
    return decorator


def timeout(seconds: float):
    """Timeout decorator"""
    def decorator(func):
        timeout_handler = TimeoutHandler(seconds)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return timeout_handler.execute(func, *args, **kwargs)
        return wrapper
    return decorator


def resilient(service_name: str, circuit_breaker_config: dict = None, 
             retry_config: dict = None, bulkhead_config: dict = None, timeout_seconds: float = 30.0):
    """Combined resilience decorator"""
    def decorator(func):
        cb_config = CircuitBreakerConfig(**circuit_breaker_config) if circuit_breaker_config else None
        r_config = RetryConfig(**retry_config) if retry_config else None
        b_config = BulkheadConfig(**bulkhead_config) if bulkhead_config else None
        
        caller = ResilientServiceCaller(
            service_name=service_name,
            circuit_breaker_config=cb_config,
            retry_config=r_config,
            bulkhead_config=b_config,
            timeout=timeout_seconds
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return caller.call(func, *args, **kwargs)
        return wrapper
    return decorator


# Global resilience manager
class ResilienceManager:
    """Global manager for all resilience patterns"""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, AdvancedCircuitBreaker] = {}
        self.bulkheads: Dict[str, Bulkhead] = {}
        self.chaos_engine = ChaosEngineeringEngine()
    
    def get_circuit_breaker(self, name: str, config: CircuitBreakerConfig = None) -> AdvancedCircuitBreaker:
        """Get or create circuit breaker"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = AdvancedCircuitBreaker(name, config)
        return self.circuit_breakers[name]
    
    def get_bulkhead(self, name: str, config: BulkheadConfig = None) -> Bulkhead:
        """Get or create bulkhead"""
        if name not in self.bulkheads:
            self.bulkheads[name] = Bulkhead(name, config)
        return self.bulkheads[name]
    
    def get_all_metrics(self) -> Dict:
        """Get metrics for all resilience components"""
        return {
            'circuit_breakers': {name: cb.get_metrics() for name, cb in self.circuit_breakers.items()},
            'bulkheads': {name: bh.get_metrics() for name, bh in self.bulkheads.items()},
            'chaos_experiments': self.chaos_engine.get_experiment_status()
        }
    
    def reset_all(self):
        """Reset all resilience components (for testing)"""
        for cb in self.circuit_breakers.values():
            cb._transition_to_closed()
        
        # Reset metrics
        for bh in self.bulkheads.values():
            with bh.lock:
                bh.total_calls = 0
                bh.rejected_calls = 0


# Global instance
resilience_manager = ResilienceManager()
