from collections.abc import AsyncGenerator, Generator, Sequence
from contextlib import asynccontextmanager, contextmanager
from dataclasses import replace
from typing import Any
from uuid import UUID

from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, OperationFailure

from app.services.models import AuditEntry, Campaign, OfferLink, Published, Stream
from app.services.shares import OfferState
from app.storage.errors import (
    DuplicateError,
    MissingParentError,
    StaleStreamError,
    StorageConflictError,
)
from app.storage.ports import Storage, UnitOfWork

type Document = dict[str, Any]
type Database = AsyncDatabase[Document]
type Session = AsyncClientSession | None
"""The transaction a repository takes part in; without one every call stands alone."""

WRITE_CONFLICT = 112


@contextmanager
def _conflicts() -> Generator[None]:
    """Two transactions touched one document: the later one gives way (R-CC-02)."""
    try:
        yield
    except DuplicateKeyError as error:
        message = "a record with the same identity is already stored"
        raise DuplicateError(message) from error
    except OperationFailure as error:
        if error.code != WRITE_CONFLICT:
            raise
        message = "another transaction is writing the same record"
        raise StorageConflictError(message) from error


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
        version=document["version"],
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
        "version": stream.version + 1,
    }


class MongoCampaigns:
    def __init__(self, database: Database, session: Session = None) -> None:
        self._campaigns = database["campaigns"]
        self._session = session

    async def add(self, campaign: Campaign) -> None:
        with _conflicts():
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
                },
                session=self._session,
            )

    async def get(self, campaign_id: UUID) -> Campaign | None:
        document = await self._campaigns.find_one({"_id": campaign_id}, session=self._session)
        return _campaign(document) if document else None

    async def get_by_keitaro_id(self, keitaro_id: int) -> Campaign | None:
        document = await self._campaigns.find_one({"keitaro_id": keitaro_id}, session=self._session)
        return _campaign(document) if document else None

    async def list_recent(self) -> list[Campaign]:
        cursor = self._campaigns.find(session=self._session).sort("created_at", DESCENDING)
        return [_campaign(document) async for document in cursor]


class MongoStreams:
    def __init__(self, database: Database, session: Session = None) -> None:
        self._client = database.client
        self._campaigns = database["campaigns"]
        self._streams = database["streams"]
        self._session = session

    async def get(self, stream_id: UUID) -> Stream | None:
        document = await self._streams.find_one({"_id": stream_id}, session=self._session)
        return _stream(document) if document else None

    async def list_by_campaign(self, campaign_id: UUID) -> list[Stream]:
        cursor = self._streams.find({"campaign_id": campaign_id}, session=self._session).sort(
            "position", ASCENDING
        )
        return [_stream(document) async for document in cursor]

    async def save(self, stream: Stream) -> Stream:
        return (await self.save_all([stream]))[0]

    async def save_all(self, streams: Sequence[Stream]) -> list[Stream]:
        """Write every stream in one transaction; any refusal aborts all of it."""
        if self._session is not None:
            await self._write(streams, self._session)
        else:
            async with self._client.start_session() as session:
                with _conflicts():
                    await session.with_transaction(lambda own: self._write(streams, own))
        return [replace(stream, version=stream.version + 1) for stream in streams]

    async def _write(self, streams: Sequence[Stream], session: AsyncClientSession) -> None:
        owners = {stream.campaign_id for stream in streams}
        stored = await self._campaigns.count_documents(
            {"_id": {"$in": list(owners)}}, session=session
        )
        if stored != len(owners):
            message = "a stream refers to a campaign that is not stored"
            raise MissingParentError(message)
        for stream in streams:
            with _conflicts():
                if stream.version == 0:
                    await self._streams.insert_one(_stream_document(stream), session=session)
                    continue
                replaced = await self._streams.replace_one(
                    {"_id": stream.id, "version": stream.version},
                    _stream_document(stream),
                    session=session,
                )
            if replaced.matched_count != 1:
                raise StaleStreamError(stream.id)

    async def delete(self, stream_id: UUID) -> None:
        with _conflicts():
            await self._streams.delete_one({"_id": stream_id}, session=self._session)


class MongoAudit:
    def __init__(self, database: Database, session: Session = None) -> None:
        self._entries = database["audit_log"]
        self._session = session

    async def record(self, entry: AuditEntry) -> None:
        await self._entries.insert_one(
            {
                "_id": entry.id,
                "action": entry.action,
                "created_at": entry.created_at,
                "campaign_id": entry.campaign_id,
                "stream_id": entry.stream_id,
                "details": dict(entry.details),
            },
            session=self._session,
        )

    async def list_recent(self, limit: int = 50) -> list[AuditEntry]:
        cursor = (
            self._entries.find(session=self._session).sort("created_at", DESCENDING).limit(limit)
        )
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


def create_mongo_storage(database: Database) -> Storage:
    """Persist in MongoDB: a stream is one document together with its offers (R-ST-05)."""

    @asynccontextmanager
    async def transaction() -> AsyncGenerator[UnitOfWork]:
        """One multi-document transaction; it needs a replica set (R-ST-06)."""
        async with database.client.start_session() as session:
            with _conflicts():
                async with await session.start_transaction():
                    yield UnitOfWork(
                        campaigns=MongoCampaigns(database, session),
                        streams=MongoStreams(database, session),
                        audit=MongoAudit(database, session),
                    )

    return Storage(
        campaigns=MongoCampaigns(database),
        streams=MongoStreams(database),
        audit=MongoAudit(database),
        transaction=transaction,
    )
