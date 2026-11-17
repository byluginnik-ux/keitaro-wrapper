from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase

from app.services.models import AuditEntry, Campaign, OfferLink, Published, Stream
from app.services.shares import OfferState
from app.storage.ports import Storage, UnitOfWork

type Document = dict[str, Any]
type Database = AsyncDatabase[Document]


def _campaign(document: Document) -> Campaign:
    return Campaign(
        id=document["_id"],
        keitaro_id=document["keitaro_id"],
        name=document["name"],
        alias=document["alias"],
        created_at=document["created_at"],
        country=document["country"],
        domain_id=document["domain_id"],
        group_id=document["group_id"],
        traffic_source_id=document["traffic_source_id"],
    )


def _offer(document: Document) -> OfferLink:
    published: Document | None = document["published"]
    return OfferLink(
        offer_id=document["offer_id"],
        name=document["name"],
        share=document["share"],
        pinned=document["pinned"],
        state=OfferState(document["state"]),
        published=Published(
            share=published["share"],
            state=OfferState(published["state"]),
            pinned=published["pinned"],
        )
        if published
        else None,
    )


def _offer_document(link: OfferLink) -> Document:
    published = link.published
    return {
        "offer_id": link.offer_id,
        "name": link.name,
        "share": link.share,
        "pinned": link.pinned,
        "state": link.state.value,
        "published": {
            "share": published.share,
            "state": published.state.value,
            "pinned": published.pinned,
        }
        if published
        else None,
    }


def _stream(document: Document) -> Stream:
    return Stream(
        id=document["_id"],
        campaign_id=document["campaign_id"],
        keitaro_id=document["keitaro_id"],
        name=document["name"],
        position=document["position"],
        kind=document["kind"],
        offers=tuple(_offer(offer) for offer in document["offers"]),
    )


def _stream_document(stream: Stream) -> Document:
    return {
        "_id": stream.id,
        "campaign_id": stream.campaign_id,
        "keitaro_id": stream.keitaro_id,
        "name": stream.name,
        "position": stream.position,
        "kind": stream.kind,
        "offers": [_offer_document(link) for link in stream.offers],
    }


class MongoCampaigns:
    def __init__(self, database: Database) -> None:
        self._campaigns = database["campaigns"]

    async def add(self, campaign: Campaign) -> None:
        await self._campaigns.insert_one(
            {
                "_id": campaign.id,
                "keitaro_id": campaign.keitaro_id,
                "name": campaign.name,
                "alias": campaign.alias,
                "created_at": campaign.created_at,
                "country": campaign.country,
                "domain_id": campaign.domain_id,
                "group_id": campaign.group_id,
                "traffic_source_id": campaign.traffic_source_id,
            }
        )

    async def get(self, campaign_id: UUID) -> Campaign | None:
        document = await self._campaigns.find_one({"_id": campaign_id})
        return _campaign(document) if document else None

    async def get_by_keitaro_id(self, keitaro_id: int) -> Campaign | None:
        document = await self._campaigns.find_one({"keitaro_id": keitaro_id})
        return _campaign(document) if document else None

    async def list_recent(self) -> list[Campaign]:
        cursor = self._campaigns.find().sort("created_at", DESCENDING)
        return [_campaign(document) async for document in cursor]


class MongoStreams:
    def __init__(self, database: Database) -> None:
        self._client = database.client
        self._campaigns = database["campaigns"]
        self._streams = database["streams"]

    async def get(self, stream_id: UUID) -> Stream | None:
        document = await self._streams.find_one({"_id": stream_id})
        return _stream(document) if document else None

    async def list_by_campaign(self, campaign_id: UUID) -> list[Stream]:
        cursor = self._streams.find({"campaign_id": campaign_id}).sort("position", ASCENDING)
        return [_stream(document) async for document in cursor]

    async def save(self, stream: Stream) -> Stream:
        await self.save_all([stream])
        return stream

    async def save_all(self, streams: Sequence[Stream]) -> list[Stream]:
        """Write every stream in one transaction; a missing campaign aborts all of it."""

        async def write(session: AsyncClientSession) -> None:
            owners = {stream.campaign_id for stream in streams}
            stored = await self._campaigns.count_documents(
                {"_id": {"$in": list(owners)}}, session=session
            )
            if stored != len(owners):
                message = "a stream refers to a campaign that is not stored"
                raise LookupError(message)
            for stream in streams:
                await self._streams.replace_one(
                    {"_id": stream.id}, _stream_document(stream), upsert=True, session=session
                )

        async with self._client.start_session() as session:
            await session.with_transaction(write)
        return list(streams)

    async def delete(self, stream_id: UUID) -> None:
        await self._streams.delete_one({"_id": stream_id})


class MongoAudit:
    def __init__(self, database: Database) -> None:
        self._entries = database["audit_log"]

    async def record(self, entry: AuditEntry) -> None:
        await self._entries.insert_one(
            {
                "_id": entry.id,
                "action": entry.action,
                "created_at": entry.created_at,
                "campaign_id": entry.campaign_id,
                "stream_id": entry.stream_id,
                "details": dict(entry.details),
            }
        )

    async def list_recent(self, limit: int = 50) -> list[AuditEntry]:
        cursor = self._entries.find().sort("created_at", DESCENDING).limit(limit)
        return [
            AuditEntry(
                id=document["_id"],
                action=document["action"],
                created_at=document["created_at"],
                campaign_id=document["campaign_id"],
                stream_id=document["stream_id"],
                details=document["details"],
            )
            async for document in cursor
        ]


async def prepare(database: Database) -> None:
    """Create the indexes the adapter relies on; safe to repeat."""
    await database["campaigns"].create_index("keitaro_id", unique=True)
    await database["campaigns"].create_index([("created_at", DESCENDING)])
    await database["streams"].create_index("keitaro_id", unique=True)
    await database["streams"].create_index([("campaign_id", ASCENDING), ("position", ASCENDING)])
    await database["audit_log"].create_index([("created_at", DESCENDING)])


@asynccontextmanager
async def _no_transaction() -> AsyncGenerator[UnitOfWork]:
    """Units of work are not implemented yet."""
    raise NotImplementedError
    yield


def create_mongo_storage(database: Database) -> Storage:
    """Persist in MongoDB: a stream is one document together with its offers (R-ST-05)."""
    return Storage(
        campaigns=MongoCampaigns(database),
        streams=MongoStreams(database),
        audit=MongoAudit(database),
        transaction=_no_transaction,
    )
