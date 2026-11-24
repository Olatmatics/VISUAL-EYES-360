"""Optional Redis cache for device-ingest deduplication and presence.

Redis is optional in development and tests. When it is unavailable, callers
fall back to the existing database-backed deduplication, so nothing breaks.
"""

import logging
import threading
from typing import Any

from app.core.config import settings

logger = logging.getLogger("ve360.cache")

_client: Any = None
_disabled = False
_init_lock = threading.Lock()


def _get_client():
    global _client, _disabled
    if _disabled:
        return None
    if _client is None:
        # One probe only: concurrent requests must not each try to connect.
        with _init_lock:
            if _client is None and not _disabled:
                if not settings.REDIS_URL:
                    _disabled = True
                    return None
                try:
                    import redis

                    client = redis.Redis.from_url(
                        settings.REDIS_URL,
                        socket_connect_timeout=0.2,
                        socket_timeout=0.2,
                        decode_responses=True,
                    )
                    client.ping()
                    _client = client
                except Exception as exc:  # Redis is an optimisation, not a dependency
                    logger.warning("Redis unavailable; using database dedupe only: %s", exc)
                    _disabled = True
    return _client


def cache_get(key: str) -> str | None:
    client = _get_client()
    if client is None:
        return None
    try:
        value = client.get(key)
    except Exception:
        return None
    return str(value) if value is not None else None


def cache_set(key: str, value: str, ttl_seconds: int) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(key, ttl_seconds, value)
    except Exception:
        pass


def close_cache() -> None:
    global _client, _disabled
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = None
    _disabled = False
