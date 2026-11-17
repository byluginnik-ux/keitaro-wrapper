import asyncio
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.cache.ports import CacheUnavailableError
from app.cache.redis import RedisCache, open_redis_cache
from tests.cache.conftest import redis_url

pytestmark = pytest.mark.anyio


async def loaded() -> str:
    return "value"


async def test_lock_of_a_vanished_loader_is_taken_over() -> None:
    """R-CH-03: whoever held the lock died before putting the value."""
    client = Redis.from_url(redis_url(), decode_responses=True)  # pyright: ignore[reportUnknownMemberType]
    prefix = f"test:{uuid4().hex[:8]}:"
    try:
        await client.set(f"{prefix}lock:list", "somebody-else", px=150)
        cache = RedisCache(client, prefix=prefix, wait=0.02)

        async with asyncio.timeout(2):
            assert await cache.get_or_load("list", 30, loaded) == "value"
    finally:
        await client.aclose()


async def test_two_processes_share_one_value() -> None:
    """R-CH-02."""
    prefix = f"test:{uuid4().hex[:8]}:"
    asked = 0

    async def counted() -> str:
        nonlocal asked
        asked += 1
        return "value"

    async with (
        open_redis_cache(redis_url(), prefix=prefix) as first,
        open_redis_cache(redis_url(), prefix=prefix) as second,
    ):
        await first.get_or_load("list", 30, counted)
        await second.get_or_load("list", 30, counted)

    assert asked == 1


async def test_unreachable_redis_is_reported_as_an_unavailable_cache() -> None:
    """R-CH-04: nothing listens on this port of the test machine itself."""
    async with open_redis_cache("redis://127.0.0.1:1/0") as cache:
        with pytest.raises(CacheUnavailableError):
            await cache.get_or_load("list", 30, loaded)
        with pytest.raises(CacheUnavailableError):
            await cache.drop("list")
        with pytest.raises(CacheUnavailableError):
            await cache.ping()
