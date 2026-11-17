import asyncio
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import UUID

from app.services.models import AuditEntry, Campaign, Stream
from app.storage.errors import DuplicateError, MissingParentError, StaleStreamError
from app.storage.pending import PendingOutbox, PendingTasks
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


def create_memory_storage() -> Storage:
    """Keep everything in process memory: for tests and for running without a database."""
    campaigns = MemoryCampaigns()
    streams = MemoryStreams(campaigns)
    audit = MemoryAudit()
    turn = asyncio.Lock()

    @asynccontextmanager
    async def transaction() -> AsyncGenerator[UnitOfWork]:
        """One unit of work at a time; a failure puts everything back."""
        async with turn:
            before = (dict(campaigns.items), dict(streams.items), list(audit.entries))
            try:
                yield UnitOfWork(
                    campaigns=campaigns,
                    streams=streams,
                    audit=audit,
                    tasks=PendingTasks(),
                    outbox=PendingOutbox(),
                )
            except BaseException:
                campaigns.items, streams.items, audit.entries = before
                raise

    return Storage(
        campaigns=campaigns,
        streams=streams,
        audit=audit,
        tasks=PendingTasks(),
        outbox=PendingOutbox(),
        transaction=transaction,
    )
