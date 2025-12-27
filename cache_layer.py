#!/home/wil/manny-mcp/venv/bin/python
"""
Caching Layer for MCP Tools (Phase 3)

Provides in-memory caching for frequently accessed data like:
- Command lists
- Class summaries
- Section lists
- File metadata

Implements TTL-based expiration and LRU eviction.
"""

import time
from typing import Any, Optional, Dict
from collections import OrderedDict
import hashlib
import json


class CacheEntry:
    """Single cache entry with TTL and metadata."""

    def __init__(self, value: Any, ttl_seconds: int = 300):
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.access_count = 0
        self.last_accessed = time.time()

    def is_expired(self) -> bool:
        """Check if entry has exceeded TTL."""
        return (time.time() - self.created_at) > self.ttl_seconds

    def access(self) -> Any:
        """Mark as accessed and return value."""
        self.access_count += 1
        self.last_accessed = time.time()
        return self.value


class LRUCache:
    """
    LRU cache with TTL expiration.

    Features:
    - Time-based expiration (TTL)
    - Least Recently Used eviction when full
    - Cache hit/miss statistics
    """

    def __init__(self, max_size: int = 100, default_ttl: int = 300):
        """
        Initialize cache.

        Args:
            max_size: Maximum number of entries (default: 100)
            default_ttl: Default time-to-live in seconds (default: 5 minutes)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def _make_key(self, func_name: str, *args, **kwargs) -> str:
        """Generate cache key from function name and arguments."""
        # Create hashable representation
        key_data = {
            "func": func_name,
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Returns:
            Cached value if found and not expired, None otherwise
        """
        if key not in self.cache:
            self.misses += 1
            return None

        entry = self.cache[key]

        # Check expiration
        if entry.is_expired():
            del self.cache[key]
            self.misses += 1
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        self.hits += 1
        return entry.access()

    def put(self, key: str, value: Any, ttl: int = None):
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to store
            ttl: Time-to-live in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl

        # Evict oldest if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            self.cache.popitem(last=False)  # Remove oldest (FIFO)

        self.cache[key] = CacheEntry(value, ttl)
        self.cache.move_to_end(key)

    def invalidate(self, pattern: str = None):
        """
        Invalidate cache entries.

        Args:
            pattern: If provided, only invalidate keys containing this pattern.
                     If None, clear entire cache.
        """
        if pattern is None:
            self.cache.clear()
        else:
            keys_to_remove = [k for k in self.cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self.cache[key]

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 2),
            "total_requests": total_requests
        }


# Global cache instances
_tool_cache: Optional[LRUCache] = None


def get_tool_cache() -> LRUCache:
    """Get or create global tool cache."""
    global _tool_cache
    if _tool_cache is None:
        _tool_cache = LRUCache(max_size=100, default_ttl=300)  # 5 minute TTL
    return _tool_cache


def cached_tool(ttl: int = 300):
    """
    Decorator for caching tool results.

    Usage:
        @cached_tool(ttl=60)
        def expensive_function(arg1, arg2):
            return ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_tool_cache()
            key = cache._make_key(func.__name__, *args, **kwargs)

            # Try cache first
            result = cache.get(key)
            if result is not None:
                return result

            # Cache miss - compute and store
            result = func(*args, **kwargs)
            cache.put(key, result, ttl=ttl)
            return result

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.cache_clear = lambda: get_tool_cache().invalidate(func.__name__)
        return wrapper
    return decorator
