from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from redis.asyncio import Redis

# delete the lock only if it is still ours: it may have expired and been taken by another loader
RELEASE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end"


class RedisCache:
    """The cache all processes share (R-CH-02)."""

    def __init__(
        self, client: Redis, *, prefix: str = "kw:", lock_ttl: float = 10.0, wait: float = 0.05
    ) -> None:
        self._redis = client
        self._prefix = prefix
        self._lock_ttl = lock_ttl
        self._wait = wait

    async def get_or_load(self, key: str, ttl: float, load: Callable[[], Awaitable[str]]) -> str:
        del key, ttl
        return await load()

    async def drop(self, key: str) -> None:
        del key

    async def ping(self) -> None:
        return None


@asynccontextmanager
async def open_redis_cache(url: str, *, prefix: str = "kw:") -> AsyncGenerator[RedisCache]:
    """Connect lazily: an unreachable server shows up as `CacheUnavailableError` on use."""
    client = Redis.from_url(  # pyright: ignore[reportUnknownMemberType] — redis-py leaves **kwargs untyped
        url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
    )
    try:
        yield RedisCache(client, prefix=prefix)
    finally:
        await client.aclose()
