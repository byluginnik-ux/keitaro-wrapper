from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.services.models import AuditEntry, Campaign, Stream


class CampaignRepository(Protocol):
    async def add(self, campaign: Campaign) -> None:
        """Store a new campaign; a known ID or tracker ID is a `DuplicateError`."""
        ...

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

    async def save(self, stream: Stream) -> Stream:
        """Write a stream with its offers if nobody wrote it since it was read (R-CC-02).

        `stream.version` is the version it was read with, 0 for a new one. The stored
        version becomes one more and comes back in the result; a mismatch is a
        `StorageConflictError` and changes nothing (R-ST-05).
        """
        ...

    async def save_all(self, streams: Sequence[Stream]) -> list[Stream]:
        """Save several streams in one atomic step, each under the rule of `save`."""
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
class UnitOfWork:
    """Repositories that share one transaction (R-ST-06).

    Everything written through them is applied together or not at all.
    """

    campaigns: CampaignRepository
    streams: StreamRepository
    audit: AuditLog


@dataclass(frozen=True, slots=True)
class Storage:
    """Everything services persist; one instance per process (R-ST-01).

    The repositories here commit every call on its own. `transaction()` opens a
    unit of work: it commits when the block ends and rolls back when it raises.
    Nothing slow belongs inside the block — no calls to the tracker.
    """

    campaigns: CampaignRepository
    streams: StreamRepository
    audit: AuditLog
    transaction: Callable[[], AbstractAsyncContextManager[UnitOfWork]]
