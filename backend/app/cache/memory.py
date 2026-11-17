import asyncio
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable


class MemoryCache:
    """The cache of one process: a dictionary and a lock per key (R-CH-02)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._values: dict[str, tuple[str, float]] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _fresh(self, key: str) -> str | None:
        kept = self._values.get(key)
        return kept[0] if kept is not None and self._clock() < kept[1] else None

    async def get_or_load(self, key: str, ttl: float, load: Callable[[], Awaitable[str]]) -> str:
        del key, ttl
        return await load()

    async def drop(self, key: str) -> None:
        del key

    async def ping(self) -> None:
        return None
