"""
Core utilities initialization.
Exports high-performance components for the ERP system.
"""
from backend.app.core.localization import MyanmarLocalization
from backend.app.core.io_engine import OptimizedIO
from backend.app.core.cache_engine import CacheEngine
from backend.app.core.rate_limiter import SlidingWindowLimiter

__all__ = [
    "MyanmarLocalization",
    "OptimizedIO",
    "CacheEngine",
    "SlidingWindowLimiter",
]
