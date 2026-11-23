"""
High-performance cache engine with binary serialization.
Uses msgpack for speed and zlib for compression on large payloads.
"""
import msgpack
import zlib
import redis.asyncio as redis

from app.config import settings


class CacheEngine:
    """Binary-optimized Redis cache with automatic compression."""
    
    PREFIX = "erp:v2:"  # Strict namespace versioning
    COMPRESSION_THRESHOLD = 1024  # Compress if > 1KB

    def __init__(self, url: str | None = None):
        # Single source of truth: settings.REDIS_URL (works in local dev and Docker)
        self.client = redis.from_url(
            url or settings.REDIS_URL,
            decode_responses=False,  # Keep binary for performance
            socket_connect_timeout=1,
            socket_keepalive=True,
            retry_on_timeout=True,
        )

    async def set(self, key: str, value: any, ttl: int = 300):
        """Binary pack with automatic compression."""
        packed = msgpack.packb(value, use_bin_type=True)
        
        # Compress if payload is large enough to benefit
        if len(packed) > self.COMPRESSION_THRESHOLD:
            compressed = zlib.compress(packed)
            # Only use compression if it actually saves space
            if len(compressed) < len(packed):
                packed = b'\x01' + compressed  # Marker \x01 = compressed
            else:
                packed = b'\x00' + packed  # Marker \x00 = uncompressed
        else:
            packed = b'\x00' + packed  # Marker \x00 = uncompressed
        
        full_key = f"{self.PREFIX}{key}"
        await self.client.setex(full_key, ttl, packed)

    async def get(self, key: str):
        """Retrieve and decompress if necessary."""
        full_key = f"{self.PREFIX}{key}"
        raw = await self.client.get(full_key)
        
        if not raw:
            return None
        
        if len(raw) < 1:
            return None
            
        header = raw[0]
        payload = raw[1:]
        
        if header == 1:  # Compressed
            payload = zlib.decompress(payload)
        
        return msgpack.unpackb(payload, raw=False)

    async def delete(self, key: str):
        """Delete a key from cache."""
        full_key = f"{self.PREFIX}{key}"
        return await self.client.delete(full_key)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        full_key = f"{self.PREFIX}{key}"
        return await self.client.exists(full_key) > 0
