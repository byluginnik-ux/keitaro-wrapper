from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.keitaro.gateway import KeitaroGateway
from app.services.catalog import CatalogService
from app.services.creator import utc_now
from app.services.models import Campaign, Stream
from app.storage.ports import Storage


@dataclass(frozen=True, slots=True)
class FetchedStreams:
    campaign: Campaign
    streams: list[Stream]


class EditorService:
    """Keep a local draft of every stream and reconcile it with the tracker (R-ED-01…24)."""

    def __init__(
        self,
        keitaro: KeitaroGateway,
        catalog: CatalogService,
        storage: Storage,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._keitaro = keitaro
        self._catalog = catalog
        self._storage = storage
        self._clock = clock

    async def campaigns(self) -> list[Campaign]:
        raise NotImplementedError

    async def campaign(self, campaign_id: UUID) -> Campaign | None:
        raise NotImplementedError

    async def streams(self, campaign_id: UUID) -> list[Stream]:
        raise NotImplementedError

    async def fetch(self, keitaro_campaign_id: int) -> FetchedStreams:
        """Load the streams of a campaign from the tracker and reconcile them with ours."""
        raise NotImplementedError
