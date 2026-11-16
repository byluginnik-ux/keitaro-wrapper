import time
from collections.abc import Callable

from app.keitaro.gateway import KeitaroGateway
from app.keitaro.models import Domain, Group, Offer, TrafficSource

DEFAULT_OFFER_LIMIT = 20


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

    async def domains(self) -> list[Domain]:
        raise NotImplementedError

    async def groups(self) -> list[Group]:
        raise NotImplementedError

    async def traffic_sources(self) -> list[TrafficSource]:
        raise NotImplementedError

    async def search_offers(self, query: str = "", limit: int = DEFAULT_OFFER_LIMIT) -> list[Offer]:
        raise NotImplementedError

    async def get_offer(self, offer_id: int) -> Offer | None:
        raise NotImplementedError
