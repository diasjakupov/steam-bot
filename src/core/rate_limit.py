from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """Simple in-memory token bucket rate limiter."""

    def __init__(self, capacity: float, refill_rate: float) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_update = time.time()

    async def acquire(self, tokens: float = 1.0, timeout: float = 10.0) -> bool:
        """
        Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait for tokens

        Returns:
            True if tokens were acquired, False if timeout occurred
        """
        deadline = time.monotonic() + timeout
        while True:
            now = time.time()
            # Refill tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            if time.monotonic() > deadline:
                return False

            # Wait before trying again
            await asyncio.sleep(1 / max(self.refill_rate, 1.0))


def build_bucket(rps: float) -> TokenBucket:
    """
    Build a token bucket with the given requests per second rate.

    Args:
        rps: Requests per second (refill rate)

    Returns:
        Configured TokenBucket instance
    """
    capacity = max(1.0, rps * 2)
    return TokenBucket(capacity=capacity, refill_rate=rps)

