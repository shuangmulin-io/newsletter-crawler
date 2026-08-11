import time
import random
import functools
import logging

logger = logging.getLogger(__name__)

class CircuitBreakerOpenException(Exception):
    """Exception raised when the circuit breaker is open and blocks calls."""
    pass

def retry_with_backoff(max_retries=3, base_delay=2.0, max_delay=30.0, exceptions=(Exception,)):
    """
    Decorator that retries a function using exponential backoff with jitter.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries. Error: {e}")
                        raise e
                    # Apply exponential backoff with jitter
                    jitter = random.uniform(0.8, 1.2)
                    sleep_time = min(delay * jitter, max_delay)
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}). Retrying in {sleep_time:.2f}s... Error: {e}")
                    time.sleep(sleep_time)
                    delay *= 2
        return wrapper
    return decorator

class CircuitBreaker:
    """
    Circuit Breaker pattern implementation to prevent cascading downstream failures.
    """
    def __init__(self, failure_threshold=5, recovery_timeout=60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.failures = 0
        self.last_failure_time = 0.0

    def observe_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(f"Circuit breaker tripped to OPEN! Threshold: {self.failure_threshold} failures.")

    def observe_success(self):
        self.failures = 0
        self.state = "CLOSED"

    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            # Check if recovery timeout has elapsed
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF-OPEN"
                logger.info("Circuit breaker entered HALF-OPEN state. Testing request...")
                return True
            return False
        if self.state == "HALF-OPEN":
            return True
        return False

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not self.allow_request():
                logger.warning(f"Request to {func.__name__} blocked by Circuit Breaker (State: {self.state})")
                raise CircuitBreakerOpenException(f"Circuit breaker is {self.state}")
            try:
                result = func(*args, **kwargs)
                self.observe_success()
                return result
            except Exception as e:
                if not isinstance(e, CircuitBreakerOpenException):
                    self.observe_failure()
                raise e
        return wrapper
