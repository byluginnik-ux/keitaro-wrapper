import time
from collections.abc import Callable

from app.keitaro.gateway import KeitaroGateway
from app.keitaro.models import Domain, Group, Offer, TrafficSource

DEFAULT_OFFER_LIMIT = 20
ACTIVE = "active"


class CatalogService:
    """Reference data of the tracker: domains, groups, traffic sources and offers."""

    def __init__(
        self,
        keitaro: KeitaroGateway,
        *,
        offers_ttl: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._keitaro = keitaro
        self._offers_ttl = offers_ttl
        self._clock = clock
        self._offers: list[Offer] = []
        self._offers_loaded_at: float | None = None

    async def domains(self) -> list[Domain]:
        return await self._keitaro.list_domains()

    async def groups(self) -> list[Group]:
        return await self._keitaro.list_groups()

    async def traffic_sources(self) -> list[TrafficSource]:
        return await self._keitaro.list_traffic_sources()

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
        now = self._clock()
        stale = self._offers_loaded_at is None or now - self._offers_loaded_at >= self._offers_ttl
        if stale:
            offers = await self._keitaro.list_offers()
            self._offers = [offer for offer in offers if offer.state == ACTIVE]
            self._offers_loaded_at = now
        return self._offers
