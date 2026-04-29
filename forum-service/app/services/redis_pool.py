"""
Shared Redis connection pool for the forum service.
Reused by: user cache, event publisher, and any future Redis needs.

Resilience: If Redis is unreachable on startup, provides a DummyRedis
that no-ops all operations so the service can still start and serve
requests (without caching / pub-sub).
"""
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("redis_pool")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_pool = None
_use_dummy = False


def _init_pool():
    """Try to create a real Redis pool; fall back to DummyRedis on failure."""
    global _pool, _use_dummy
    try:
        from redis.asyncio import ConnectionPool
        _pool = ConnectionPool.from_url(REDIS_URL, max_connections=20, decode_responses=True)
        _use_dummy = False
        logger.info("Redis pool created (%s)", REDIS_URL)
    except Exception as exc:
        logger.warning("Cannot create Redis pool (%s), using DummyRedis fallback", exc)
        _use_dummy = True


_init_pool()


# ── DummyRedis: no-op replacement when Redis is down ─────────────────
class _DummyPipeline:
    """Pipeline that silently discards all commands."""
    def setex(self, *a, **kw):
        return self
    def delete(self, *a, **kw):
        return self
    async def execute(self):
        return []


class DummyRedis:
    """
    Drop-in async Redis replacement that no-ops everything.
    Allows the app to run (without cache) when Redis is unavailable.
    """
    async def mget(self, *keys):
        return [None] * len(keys)

    async def get(self, key):
        return None

    async def setex(self, key, ttl, value):
        pass

    async def publish(self, channel, message):
        raise ConnectionError("DummyRedis: Redis unavailable")

    async def xadd(self, stream, fields, *args, **kwargs):
        raise ConnectionError("DummyRedis: Redis unavailable")

    async def ping(self):
        raise ConnectionError("DummyRedis: Redis unavailable")

    def pipeline(self):
        return _DummyPipeline()


_dummy_instance = DummyRedis()


def get_redis():
    """Return a Redis client backed by the shared pool, or DummyRedis."""
    if _use_dummy or _pool is None:
        return _dummy_instance
    try:
        from redis.asyncio import Redis
        return Redis(connection_pool=_pool)
    except Exception:
        return _dummy_instance
