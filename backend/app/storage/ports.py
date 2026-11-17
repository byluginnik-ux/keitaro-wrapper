from collections.abc import Callable, Collection, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.services.models import (
    AuditEntry,
    Campaign,
    OutboxBacklog,
    OutboxMessage,
    Stream,
    Task,
    TaskKind,
    TaskStatus,
)


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


class TaskRepository(Protocol):
    async def add(self, task: Task) -> None:
        """Store a new task; a known ID is a `DuplicateError` (R-TK-03)."""
        ...

    async def get(self, task_id: UUID) -> Task | None: ...
    async def save(self, task: Task, *, was: TaskStatus) -> None:
        """Replace the task if it is stored in the status `was` (R-TK-02).

        Anything else, a missing task included, is a `StaleTaskError`.
        """
        ...

    async def list_recent(
        self,
        *,
        statuses: Collection[TaskStatus] = (),
        kind: TaskKind | None = None,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[Task]:
        """Return tasks newest first; `before` continues a listing from its last task."""
        ...

    async def count_by_status(self) -> dict[TaskStatus, int]:
        """Count the tasks in every status that has any."""
        ...


class Outbox(Protocol):
    async def put(self, message: OutboxMessage) -> None:
        """Queue a message; inside a unit of work it leaves only if the work commits."""
        ...

    async def claim(self, *, limit: int, now: datetime, lease: timedelta) -> list[OutboxMessage]:
        """Take the oldest unsent messages for `lease`, out of everybody else's reach (R-EV-02)."""
        ...

    async def mark_sent(self, ids: Sequence[UUID], now: datetime) -> None: ...
    async def backlog(self) -> OutboxBacklog: ...


@dataclass(frozen=True, slots=True)
class UnitOfWork:
    """Repositories that share one transaction (R-ST-06).

    Everything written through them is applied together or not at all.
    """

    campaigns: CampaignRepository
    streams: StreamRepository
    audit: AuditLog
    tasks: TaskRepository
    outbox: Outbox


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
    tasks: TaskRepository
    outbox: Outbox
    transaction: Callable[[], AbstractAsyncContextManager[UnitOfWork]]
