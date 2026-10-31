"""Fixed-window rate limiting backed by Redis (or memory when Redis isn't configured)."""

import time
from collections import defaultdict

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.errors import too_many_requests


class RateLimiter:
    def __init__(self, redis_url: str | None):
        self._redis = Redis.from_url(redis_url) if redis_url else None
        self._memory: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))

    async def hit(self, key: str, limit: int, window_seconds: int) -> None:
        """Count one request against ``key``; raise 429 once ``limit`` is exceeded."""
        if self._redis is not None:
            redis_key = f"rl:{key}"
            count = await self._redis.incr(redis_key)
            if count == 1:
                await self._redis.expire(redis_key, window_seconds)
            if count > limit:
                ttl = await self._redis.ttl(redis_key)
                raise too_many_requests(max(int(ttl), 1))
            return

        now = time.monotonic()
        count, started = self._memory[key]
        if now - started >= window_seconds:
            count, started = 0, now
        count += 1
        self._memory[key] = (count, started)
        if count > limit:
            raise too_many_requests(max(int(window_seconds - (now - started)), 1))

    def reset(self) -> None:
        self._memory.clear()


rate_limiter = RateLimiter(get_settings().redis_url)
