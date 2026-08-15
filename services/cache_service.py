import os
import time
import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Cache TTL Configuration with safe fallback
def get_cache_ttl() -> int:
    """Retrieve and validate cache TTL (in seconds) from environment variable."""
    raw_ttl = os.getenv("WEATHER_CACHE_TTL", "600").strip()
    try:
        ttl = int(raw_ttl)
        return ttl if ttl > 0 else 600
    except ValueError:
        logger.warning(f"Invalid WEATHER_CACHE_TTL value '{raw_ttl}'. Falling back to default 600s.")
        return 600


class InMemoryCache:
    """Simple thread-safe in-memory cache with TTL expiration."""

    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache if it exists and has not expired."""
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None

            value, expires_at = entry
            if time.time() > expires_at:
                # Cache expired -> remove and return None
                del self._store[key]
                return None

            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store value in cache with expiration timestamp."""
        if ttl is None:
            ttl = get_cache_ttl()

        expires_at = time.time() + ttl
        with self._lock:
            self._store[key] = (value, expires_at)

    def delete(self, key: str) -> bool:
        """Delete specific key from cache."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries from cache."""
        with self._lock:
            self._store.clear()


# Global Singleton Cache Instance
_cache_instance = InMemoryCache()


def get_cached(key: str) -> Optional[Any]:
    """Retrieve cached item by key."""
    return _cache_instance.get(key)


def set_cached(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """Store item in cache."""
    _cache_instance.set(key, value, ttl)


def delete_cached(key: str) -> bool:
    """Delete item from cache."""
    return _cache_instance.delete(key)


def clear_cache() -> None:
    """Clear all cached items."""
    _cache_instance.clear()


# Key Normalization Helpers
def make_city_cache_key(prefix: str, city: str) -> str:
    """Generate normalized cache key for city-based queries (e.g. 'weather:city:lahore')."""
    normalized_city = city.strip().lower()
    return f"{prefix}:city:{normalized_city}"


def make_coords_cache_key(prefix: str, lat: float, lon: float) -> str:
    """Generate normalized cache key for coordinate queries (e.g. 'weather:coords:31.5204:74.3587')."""
    round_lat = round(float(lat), 4)
    round_lon = round(float(lon), 4)
    return f"{prefix}:coords:{round_lat}:{round_lon}"
