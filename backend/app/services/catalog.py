import time
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import TypeAdapter

from app.cache.memory import MemoryCache
from app.cache.ports import Cache, CacheUnavailableError
from app.keitaro.gateway import KeitaroGateway
from app.keitaro.models import Domain, Group, Offer, TrafficSource

DEFAULT_OFFER_LIMIT = 20
ACTIVE = "active"

DOMAINS = TypeAdapter(list[Domain])
GROUPS = TypeAdapter(list[Group])
SOURCES = TypeAdapter(list[TrafficSource])
OFFERS = TypeAdapter(list[Offer])


class CatalogService:
    """Reference data of the tracker, read through a cache (R-CH-01)."""

    def __init__(
        self,
        keitaro: KeitaroGateway,
        cache: Cache | None = None,
        *,
        ttl: float = 30.0,
        offers_ttl: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._keitaro = keitaro
        self._cache = cache or MemoryCache(clock)
        self._ttl = ttl
        self._offers_ttl = ttl if offers_ttl is None else offers_ttl
        # the text last seen in the cache and what it was parsed into, per list
        self._parsed: dict[str, tuple[str, list[Any]]] = {}

    async def domains(self) -> list[Domain]:
        return await self._kept("domains", DOMAINS, self._ttl, self._keitaro.list_domains)

    async def forget_domains(self) -> None:
        """Drop the cached domains: one was created and the next reader must see it (R-CH-05)."""
        try:
            await self._cache.drop("domains")
        except CacheUnavailableError:
            return  # nothing is cached where the cache cannot be reached

    async def groups(self) -> list[Group]:
        return await self._kept("groups", GROUPS, self._ttl, self._keitaro.list_groups)

    async def traffic_sources(self) -> list[TrafficSource]:
        return await self._kept(
            "traffic_sources", SOURCES, self._ttl, self._keitaro.list_traffic_sources
        )

    async def search_offers(self, query: str = "", limit: int = DEFAULT_OFFER_LIMIT) -> list[Offer]:
        """Find active offers by name fragment or ID prefix (R-KT-07)."""
        needle = query.strip().casefold()
        matches = (
            offer
            for offer in await self._active_offers()
            if needle in offer.name.casefold() or str(offer.id).startswith(needle)
        )
        return [offer for offer, _ in zip(matches, range(limit), strict=False)]

    async def get_offer(self, offer_id: int) -> Offer | None:
        return next((offer for offer in await self._active_offers() if offer.id == offer_id), None)

    async def _active_offers(self) -> list[Offer]:
        """Keep the list briefly: the tracker has no search and returns everything."""

        async def active() -> list[Offer]:
            return [offer for offer in await self._keitaro.list_offers() if offer.state == ACTIVE]

        return await self._kept("offers", OFFERS, self._offers_ttl, active)

    async def _kept[T](
        self,
        key: str,
        shape: TypeAdapter[list[T]],
        ttl: float,
        read: Callable[[], Awaitable[list[T]]],
    ) -> list[T]:
        """Read a list through the cache; without the cache, straight from the tracker (R-CH-04)."""

        async def load() -> str:
            return shape.dump_json(await read()).decode()

        try:
            text = await self._cache.get_or_load(key, ttl, load)
        except CacheUnavailableError:
            return await read()
        seen = self._parsed.get(key)
        if seen is not None and seen[0] == text:
            return seen[1]
        parsed = shape.validate_json(text)
        self._parsed[key] = (text, parsed)
        return parsed
