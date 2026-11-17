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
        cached = self._fresh(key)
        if cached is not None:
            return cached
        async with self._locks[key]:
            # whoever waited for the lock finds the value its holder has just put
            cached = self._fresh(key)
            if cached is not None:
                return cached
            value = await load()
            if ttl > 0:
                self._values[key] = (value, self._clock() + ttl)
            return value

    async def drop(self, key: str) -> None:
        self._values.pop(key, None)

    async def ping(self) -> None:
        return None
