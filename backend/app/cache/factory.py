from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.cache.memory import MemoryCache
from app.cache.ports import Cache
from app.cache.redis import open_redis_cache
from app.settings import Settings


@asynccontextmanager
async def open_cache(settings: Settings) -> AsyncGenerator[Cache]:
    """Open the cache chosen by CACHE_BACKEND (R-CH-02)."""
    if settings.cache_backend == "redis":
        async with open_redis_cache(settings.redis_url) as shared:
            yield shared
        return
    yield MemoryCache()
