"""
Sliding window rate limiter for DDoS protection and API throttling.
Uses Redis sorted sets for O(log N) performance.
"""
import time
import redis.asyncio as redis

from app.config import settings

class SlidingWindowLimiter:
    """Production-grade rate limiter with sliding window algorithm."""

    PREFIX = "rate:"

    def __init__(self, url: str | None = None):
        # Single source of truth: settings.REDIS_URL (works in local dev and Docker)
        self.redis = redis.from_url(
            url or settings.REDIS_URL,
            socket_connect_timeout=1,
            socket_keepalive=True,
        )

    async def is_allowed(self, identifier: str, limit: int, window: int = 60) -> bool:
        """
        Check if request is allowed under rate limit.
        
        Args:
            identifier: Unique key (e.g., user_id, ip_address)
            limit: Max requests per window
            window: Time window in seconds
            
        Returns:
            True if allowed, False if rate limited
        """
        key = f"{self.PREFIX}{identifier}"
        now = time.time()
        window_start = now - window
        
        pipe = self.redis.pipeline()
        
        # Remove old entries outside the window
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Add current request timestamp
        pipe.zadd(key, {str(now): now})
        
        # Count requests in current window
        pipe.zcard(key)
        
        # Set expiry to clean up automatically
        pipe.expire(key, window)
        
        results = await pipe.execute()
        count = results[2]  # Result of zcard
        
        return count <= limit

    async def get_remaining(self, identifier: str, limit: int, window: int = 60) -> int:
        """Get remaining requests allowed in current window."""
        key = f"{self.PREFIX}{identifier}"
        now = time.time()
        window_start = now - window
        
        # Clean old entries first
        await self.redis.zremrangebyscore(key, 0, window_start)
        
        count = await self.redis.zcard(key)
        return max(0, limit - count)

    async def reset(self, identifier: str):
        """Manually reset rate limit for an identifier."""
        key = f"{self.PREFIX}{identifier}"
        return await self.redis.delete(key)
