import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from typing import cast
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.cache.ports import CacheUnavailableError

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
        name, lock, token = self._prefix + key, f"{self._prefix}lock:{key}", uuid4().hex
        while True:
            try:
                cached = cast("str | None", await self._redis.get(name))
                if cached is not None:
                    return cached
                mine = await self._redis.set(lock, token, nx=True, px=int(self._lock_ttl * 1000))
            except RedisError as error:
                raise CacheUnavailableError(str(error)) from error
            if mine:
                break
            # somebody else is loading: the value appears soon, or their lock expires (R-CH-03)
            await asyncio.sleep(self._wait)
        try:
            value = await load()
            if ttl > 0:
                with suppress(RedisError):  # the value is in hand; keeping it is optional
                    await self._redis.set(name, value, px=int(ttl * 1000))
            return value
        finally:
            with suppress(RedisError):
                await self._redis.eval(RELEASE, 1, lock, token)  # pyright: ignore[reportGeneralTypeIssues, reportUnknownMemberType] — redis-py types eval as sync or async

    async def drop(self, key: str) -> None:
        try:
            await self._redis.delete(self._prefix + key)
        except RedisError as error:
            raise CacheUnavailableError(str(error)) from error

    async def ping(self) -> None:
        try:
            await self._redis.ping()  # pyright: ignore[reportGeneralTypeIssues, reportUnknownMemberType] — redis-py types ping as sync or async
        except RedisError as error:
            raise CacheUnavailableError(str(error)) from error


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
