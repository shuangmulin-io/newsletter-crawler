import pytest
import time
from utils.resilience import retry_with_backoff, CircuitBreaker, CircuitBreakerOpenException

def test_retry_with_backoff():
    attempts = 0
    @retry_with_backoff(max_retries=2, base_delay=0.01, exceptions=(ValueError,))
    def fail_twice():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Flaky error")
        return "success"

    assert fail_twice() == "success"
    assert attempts == 3

def test_circuit_breaker():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
    
    @cb
    def call_me(should_fail=False):
        if should_fail:
            raise ValueError("Trip breaker")
        return "ok"
        
    assert call_me() == "ok"
    
    # Trigger failures to trip
    for _ in range(2):
        try:
            call_me(should_fail=True)
        except ValueError:
            pass
            
    assert cb.state == "OPEN"
    
    # Call should be blocked immediately
    with pytest.raises(CircuitBreakerOpenException):
        call_me()
        
    # Wait for recovery timeout
    time.sleep(0.15)
    
    # Should recover on next success
    assert call_me() == "ok"
    assert cb.state == "CLOSED"
