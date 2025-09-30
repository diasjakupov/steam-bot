from __future__ import annotations

import asyncio
import time
from typing import Optional

from redis.asyncio import Redis


class TokenBucket:
    """Simple Redis-backed token bucket."""

    def __init__(self, redis: Redis, key: str, capacity: float, refill_rate: float) -> None:
        self.redis = redis
        self.key = key
        self.capacity = capacity
        self.refill_rate = refill_rate

    async def acquire(self, tokens: float = 1.0, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            now = time.time()
            script = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local tokens = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])
local bucket = redis.call('HMGET', key, 'tokens', 'timestamp')
local current = tonumber(bucket[1])
local timestamp = tonumber(bucket[2])
if not current then
  current = capacity
  timestamp = now
end
local delta = math.max(0, now - timestamp)
current = math.min(capacity, current + delta * refill)
if current < tokens then
  redis.call('HMSET', key, 'tokens', current, 'timestamp', now)
  redis.call('EXPIRE', key, ttl)
  return current
else
  current = current - tokens
  redis.call('HMSET', key, 'tokens', current, 'timestamp', now)
  redis.call('EXPIRE', key, ttl)
  return current + tokens
end
"""
            ttl = max(5, int(self.capacity / max(self.refill_rate, 0.01)))
            remaining = await self.redis.eval(script, 1, self.key, self.capacity, self.refill_rate, now, tokens, ttl)
            if remaining is not None and remaining >= tokens:
                return True
            if time.monotonic() > deadline:
                return False
            await asyncio.sleep(1 / max(self.refill_rate, 1.0))


async def build_bucket(redis: Redis, key: str, rps: float) -> TokenBucket:
    capacity = max(1.0, rps * 2)
    return TokenBucket(redis, key, capacity=capacity, refill_rate=rps)

