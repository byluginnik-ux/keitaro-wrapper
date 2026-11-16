from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.services.models import AuditEntry, Campaign, Stream


class CampaignRepository(Protocol):
    async def add(self, campaign: Campaign) -> None: ...
    async def get(self, campaign_id: UUID) -> Campaign | None: ...
    async def get_by_keitaro_id(self, keitaro_id: int) -> Campaign | None: ...
    async def list_recent(self) -> list[Campaign]:
        """Return every campaign, newest first."""
        ...


class StreamRepository(Protocol):
    async def get(self, stream_id: UUID) -> Stream | None: ...
    async def list_by_campaign(self, campaign_id: UUID) -> list[Stream]:
        """Return the streams of a campaign ordered by position."""
        ...

    async def save(self, stream: Stream) -> None:
        """Insert or replace a stream together with its offers, all or nothing (R-ST-05)."""
        ...

    async def save_all(self, streams: Sequence[Stream]) -> None:
        """Save several streams in one atomic step."""
        ...

    async def delete(self, stream_id: UUID) -> None:
        """Forget a stream and its offers; an unknown ID is not an error (R-ED-08)."""
        ...


class AuditLog(Protocol):
    async def record(self, entry: AuditEntry) -> None: ...
    async def list_recent(self, limit: int = 50) -> list[AuditEntry]:
        """Return the latest entries, newest first."""
        ...


@dataclass(frozen=True, slots=True)
class Storage:
    """Everything services persist; one instance per process (R-ST-01)."""

    campaigns: CampaignRepository
    streams: StreamRepository
    audit: AuditLog
