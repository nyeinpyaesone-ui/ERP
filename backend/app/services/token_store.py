"""JWT jti denylist (revocation) backed by Redis.

Fail-open when Redis is unavailable (availability over strict revocation) —
but only attempt one connection per process: a down Redis must not add
per-request latency. Keys expire naturally with the token TTL, so the
denylist needs no cleanup job.
"""

import redis as redis_lib

from app.config import settings

_client: redis_lib.Redis | None = None
_disabled = False


def _get() -> redis_lib.Redis | None:
    global _client, _disabled
    if _disabled:
        return None
    if _client is None:
        _client = redis_lib.from_url(
            settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=0.5
        )
        try:
            _client.ping()
        except Exception:
            _client = None
            _disabled = True
            return None
    return _client


def _fail() -> None:
    global _client, _disabled
    _client = None
    _disabled = True


def _key(jti: str) -> str:
    return f"auth:revoked:{jti}"


def revoke(jti: str, ttl_seconds: int) -> bool:
    """Denylist a jti for the remainder of its lifetime."""
    if not jti or ttl_seconds <= 0:
        return False
    client = _get()
    if client is None:
        return False
    try:
        client.set(_key(jti), "1", ex=ttl_seconds)
        return True
    except Exception:
        _fail()
        return False


def is_revoked(jti: str) -> bool:
    if not jti:
        return False
    client = _get()
    if client is None:
        return False
    try:
        return bool(client.exists(_key(jti)))
    except Exception:
        _fail()
        return False


def reset_for_tests() -> None:
    """Drop the cached client/state so unit tests start clean."""
    global _client, _disabled
    _client = None
    _disabled = False
