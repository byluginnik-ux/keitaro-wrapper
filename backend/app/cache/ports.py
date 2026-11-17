from collections.abc import Awaitable, Callable
from typing import Protocol


class CacheUnavailableError(Exception):
    """The cache itself cannot be reached; the caller reads the source directly (R-CH-04)."""


class Cache(Protocol):
    """Short-lived copies of what is slow to read (R-CH-01)."""

    async def get_or_load(self, key: str, ttl: float, load: Callable[[], Awaitable[str]]) -> str:
        """Return the cached text or load it once for everybody who asks now (R-CH-03).

        A failure of `load` is raised to the caller and nothing is cached.
        """
        ...

    async def drop(self, key: str) -> None:
        """Forget the value, so the next reader loads it anew."""
        ...

    async def ping(self) -> None:
        """Raise `CacheUnavailableError` if the cache cannot be reached."""
        ...
