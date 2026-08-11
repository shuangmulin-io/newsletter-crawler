import time
from collections import defaultdict
from threading import Lock
from urllib.parse import urlparse

class TokenBucketRateLimiter:
    """
    Token bucket rate limiter to control requests per domain.
    """
    def __init__(self, max_tokens: float = 5.0, refill_rate: float = 1.0):
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate  # Tokens refilled per second
        self.tokens = defaultdict(lambda: max_tokens)
        self.last_refill = defaultdict(time.time)
        self.lock = Lock()

    def _refill(self, domain: str):
        current_time = time.time()
        elapsed = current_time - self.last_refill[domain]
        if elapsed > 0:
            new_tokens = elapsed * self.refill_rate
            self.tokens[domain] = min(self.max_tokens, self.tokens[domain] + new_tokens)
            self.last_refill[domain] = current_time

    def acquire(self, url: str) -> bool:
        """
        Attempts to acquire 1 token for the domain of the URL.
        Returns True if successful, False otherwise.
        """
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        with self.lock:
            self._refill(domain)
            if self.tokens[domain] >= 1.0:
                self.tokens[domain] -= 1.0
                return True
            return False

    def wait_if_needed(self, url: str, timeout: float = 10.0) -> bool:
        """
        Waits until a token becomes available for the domain.
        Returns True if token acquired, False if timeout reached.
        """
        start = time.time()
        while True:
            if self.acquire(url):
                return True
            if time.time() - start > timeout:
                return False
            time.sleep(0.1)
