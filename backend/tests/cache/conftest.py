import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest

from app.cache.memory import MemoryCache
from app.cache.ports import Cache
from app.cache.redis import open_redis_cache


def redis_url() -> str:
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        message = "redis: set TEST_REDIS_URL (see `docker compose --profile test up -d`)"
        if os.environ.get("REQUIRE_CACHE_TESTS"):
            pytest.fail(message)
        pytest.skip(message)
    return url


@pytest.fixture(params=["memory", "redis"])
async def cache(request: pytest.FixtureRequest) -> AsyncIterator[Cache]:
    """Every cache runs the same contract (R-CH-02); keys of a test never meet another test's."""
    if request.param == "memory":
        yield MemoryCache()
        return
    async with open_redis_cache(redis_url(), prefix=f"test:{uuid4().hex[:8]}:") as shared:
        yield shared
