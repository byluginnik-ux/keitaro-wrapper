import asyncio
from collections import Counter
from collections.abc import AsyncGenerator, Collection, Sequence
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timedelta
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
from app.storage.errors import (
    DuplicateError,
    MissingParentError,
    StaleStreamError,
    StaleTaskError,
)
from app.storage.ports import Storage, UnitOfWork


class MemoryCampaigns:
    def __init__(self) -> None:
        self.items: dict[UUID, Campaign] = {}

    async def add(self, campaign: Campaign) -> None:
        taken = campaign.id in self.items or any(
            item.keitaro_id == campaign.keitaro_id for item in self.items.values()
        )
        if taken:
            message = f"campaign {campaign.keitaro_id} is already stored"
            raise DuplicateError(message)
        self.items[campaign.id] = campaign

    async def get(self, campaign_id: UUID) -> Campaign | None:
        return self.items.get(campaign_id)

    async def get_by_keitaro_id(self, keitaro_id: int) -> Campaign | None:
        return next((item for item in self.items.values() if item.keitaro_id == keitaro_id), None)

    async def list_recent(self) -> list[Campaign]:
        return sorted(self.items.values(), key=lambda item: item.created_at, reverse=True)


class MemoryStreams:
    def __init__(self, campaigns: MemoryCampaigns) -> None:
        self._campaigns = campaigns
        self.items: dict[UUID, Stream] = {}

    async def get(self, stream_id: UUID) -> Stream | None:
        return self.items.get(stream_id)

    async def list_by_campaign(self, campaign_id: UUID) -> list[Stream]:
        found = [item for item in self.items.values() if item.campaign_id == campaign_id]
        return sorted(found, key=lambda item: item.position)

    async def save(self, stream: Stream) -> Stream:
        return (await self.save_all([stream]))[0]

    async def save_all(self, streams: Sequence[Stream]) -> list[Stream]:
        """Check every stream first, so a refusal leaves all of them as they were."""
        for stream in streams:
            if stream.campaign_id not in self._campaigns.items:
                message = f"campaign {stream.campaign_id} is not stored"
                raise MissingParentError(message)
            stored = self.items.get(stream.id)
            if (stored.version if stored else 0) != stream.version:
                raise StaleStreamError(stream.id)
            if any(
                item.keitaro_id == stream.keitaro_id and item.id != stream.id
                for item in self.items.values()
            ):
                message = f"stream {stream.keitaro_id} is already stored"
                raise DuplicateError(message)
        saved = [replace(stream, version=stream.version + 1) for stream in streams]
        self.items.update({item.id: item for item in saved})
        return saved

    async def delete(self, stream_id: UUID) -> None:
        self.items.pop(stream_id, None)


class MemoryAudit:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    async def record(self, entry: AuditEntry) -> None:
        self.entries.append(entry)

    async def list_recent(self, limit: int = 50) -> list[AuditEntry]:
        newest_first = sorted(self.entries, key=lambda entry: entry.created_at, reverse=True)
        return newest_first[:limit]


class MemoryTasks:
    def __init__(self) -> None:
        self.items: dict[UUID, Task] = {}

    async def add(self, task: Task) -> None:
        if task.id in self.items:
            message = f"task {task.id} is already stored"
            raise DuplicateError(message)
        self.items[task.id] = task

    async def get(self, task_id: UUID) -> Task | None:
        return self.items.get(task_id)

    async def save(self, task: Task, *, was: TaskStatus) -> None:
        stored = self.items.get(task.id)
        if stored is None or stored.status is not was:
            raise StaleTaskError(task.id)
        self.items[task.id] = task

    async def list_recent(
        self,
        *,
        statuses: Collection[TaskStatus] = (),
        kind: TaskKind | None = None,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[Task]:
        found = [
            task
            for task in self.items.values()
            if (not statuses or task.status in statuses)
            and (kind is None or task.kind is kind)
            and (before is None or task.created_at < before)
        ]
        return sorted(found, key=lambda task: task.created_at, reverse=True)[:limit]

    async def count_by_status(self) -> dict[TaskStatus, int]:
        return dict(Counter(task.status for task in self.items.values()))


class MemoryOutbox:
    def __init__(self) -> None:
        self.waiting: dict[UUID, OutboxMessage] = {}
        self.claimed: dict[UUID, datetime] = {}

    async def put(self, message: OutboxMessage) -> None:
        self.waiting[message.id] = message

    async def claim(self, *, limit: int, now: datetime, lease: timedelta) -> list[OutboxMessage]:
        free = [
            message for message in self.waiting.values() if self.claimed.get(message.id, now) <= now
        ]
        taken = sorted(free, key=lambda message: message.created_at)[:limit]
        self.claimed.update({message.id: now + lease for message in taken})
        return taken

    async def mark_sent(self, ids: Sequence[UUID], now: datetime) -> None:
        del now
        for message_id in ids:
            self.waiting.pop(message_id, None)
            self.claimed.pop(message_id, None)

    async def backlog(self) -> OutboxBacklog:
        oldest = min((message.created_at for message in self.waiting.values()), default=None)
        return OutboxBacklog(len(self.waiting), oldest)


def create_memory_storage() -> Storage:
    """Keep everything in process memory: for tests and for running without a database."""
    campaigns = MemoryCampaigns()
    streams = MemoryStreams(campaigns)
    audit = MemoryAudit()
    tasks = MemoryTasks()
    outbox = MemoryOutbox()
    turn = asyncio.Lock()

    @asynccontextmanager
    async def transaction() -> AsyncGenerator[UnitOfWork]:
        """One unit of work at a time; a failure puts everything back."""
        async with turn:
            before = (
                dict(campaigns.items),
                dict(streams.items),
                list(audit.entries),
                dict(tasks.items),
                dict(outbox.waiting),
            )
            try:
                yield UnitOfWork(
                    campaigns=campaigns, streams=streams, audit=audit, tasks=tasks, outbox=outbox
                )
            except BaseException:
                campaigns.items, streams.items, audit.entries, tasks.items, outbox.waiting = before
                raise

    return Storage(
        campaigns=campaigns,
        streams=streams,
        audit=audit,
        tasks=tasks,
        outbox=outbox,
        transaction=transaction,
    )
