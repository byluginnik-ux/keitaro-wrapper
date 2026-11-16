from collections.abc import Sequence
from uuid import UUID

from app.services.models import AuditEntry, Campaign, Stream
from app.storage.ports import Storage


class MemoryCampaigns:
    def __init__(self) -> None:
        self.items: dict[UUID, Campaign] = {}

    async def add(self, campaign: Campaign) -> None:
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

    async def save(self, stream: Stream) -> None:
        await self.save_all([stream])

    async def save_all(self, streams: Sequence[Stream]) -> None:
        orphans = [item for item in streams if item.campaign_id not in self._campaigns.items]
        if orphans:
            message = f"campaign {orphans[0].campaign_id} is not stored"
            raise LookupError(message)
        self.items.update({item.id: item for item in streams})


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
    return Storage(campaigns=campaigns, streams=MemoryStreams(campaigns), audit=MemoryAudit())
