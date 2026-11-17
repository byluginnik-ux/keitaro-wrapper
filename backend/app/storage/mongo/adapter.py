from collections.abc import AsyncGenerator, Collection, Generator, Sequence
from contextlib import asynccontextmanager, contextmanager
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, OperationFailure

from app.services.models import (
    AuditEntry,
    Campaign,
    OfferLink,
    OutboxBacklog,
    OutboxMessage,
    Published,
    Stream,
    Task,
    TaskKind,
    TaskStatus,
)
from app.services.shares import OfferState
from app.storage import codec
from app.storage.errors import (
    DuplicateError,
    MissingParentError,
    StaleStreamError,
    StaleTaskError,
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


def _task(document: Document) -> Task:
    return Task(
        id=document["_id"],
        kind=TaskKind(document["kind"]),
        created_at=document["created_at"],
        fingerprint=document["fingerprint"],
        payload=document["payload"],
        status=TaskStatus(document["status"]),
        attempts=document["attempts"],
        campaign_id=document["campaign_id"],
        stream_id=document["stream_id"],
        started_at=document["started_at"],
        finished_at=document["finished_at"],
        refusal=codec.refusal_from_json(document["refusal"]),
        steps=codec.steps_from_json(document["steps"]),
        retry_of=document["retry_of"],
    )


def _task_document(task: Task) -> Document:
    return {
        "_id": task.id,
        "kind": task.kind.value,
        "status": task.status.value,
        "fingerprint": task.fingerprint,
        "payload": dict(task.payload),
        "attempts": task.attempts,
        "campaign_id": task.campaign_id,
        "stream_id": task.stream_id,
        "retry_of": task.retry_of,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "refusal": codec.refusal_to_json(task.refusal),
        "steps": codec.steps_to_json(task.steps),
    }


class MongoTasks:
    def __init__(self, database: Database, session: Session = None) -> None:
        self._tasks = database["tasks"]
        self._session = session

    async def add(self, task: Task) -> None:
        with _conflicts():
            await self._tasks.insert_one(_task_document(task), session=self._session)

    async def get(self, task_id: UUID) -> Task | None:
        document = await self._tasks.find_one({"_id": task_id}, session=self._session)
        return _task(document) if document else None

    async def save(self, task: Task, *, was: TaskStatus) -> None:
        with _conflicts():
            replaced = await self._tasks.replace_one(
                {"_id": task.id, "status": was.value}, _task_document(task), session=self._session
            )
        if replaced.matched_count != 1:
            raise StaleTaskError(task.id)

    async def list_recent(
        self,
        *,
        statuses: Collection[TaskStatus] = (),
        kind: TaskKind | None = None,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[Task]:
        query: Document = {}
        if statuses:
            query["status"] = {"$in": [status.value for status in statuses]}
        if kind is not None:
            query["kind"] = kind.value
        if before is not None:
            query["created_at"] = {"$lt": before}
        cursor = (
            self._tasks.find(query, session=self._session)
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        return [_task(document) async for document in cursor]

    async def count_by_status(self) -> dict[TaskStatus, int]:
        groups = await self._tasks.aggregate(
            [{"$group": {"_id": "$status", "count": {"$sum": 1}}}], session=self._session
        )
        return {TaskStatus(group["_id"]): group["count"] async for group in groups}


class MongoOutbox:
    def __init__(self, database: Database, session: Session = None) -> None:
        self._outbox = database["outbox"]
        self._session = session

    async def put(self, message: OutboxMessage) -> None:
        await self._outbox.insert_one(
            {
                "_id": message.id,
                "topic": message.topic,
                "payload": dict(message.payload),
                "created_at": message.created_at,
                "claimed_until": None,
                "sent_at": None,
            },
            session=self._session,
        )

    async def claim(self, *, limit: int, now: datetime, lease: timedelta) -> list[OutboxMessage]:
        """Take messages one by one (R-EV-02).

        Each find-and-update is atomic, so no two senders get the same message.
        """
        free = {
            "sent_at": None,
            "$or": [{"claimed_until": None}, {"claimed_until": {"$lte": now}}],
        }
        taken: list[OutboxMessage] = []
        while len(taken) < limit:
            document = await self._outbox.find_one_and_update(
                free,
                {"$set": {"claimed_until": now + lease}},
                sort=[("created_at", ASCENDING), ("_id", ASCENDING)],
                return_document=ReturnDocument.AFTER,
                session=self._session,
            )
            if document is None:
                break
            taken.append(
                OutboxMessage(
                    id=document["_id"],
                    topic=document["topic"],
                    created_at=document["created_at"],
                    payload=document["payload"],
                )
            )
        return taken

    async def mark_sent(self, ids: Sequence[UUID], now: datetime) -> None:
        await self._outbox.update_many(
            {"_id": {"$in": list(ids)}}, {"$set": {"sent_at": now}}, session=self._session
        )

    async def backlog(self) -> OutboxBacklog:
        waiting = await self._outbox.count_documents({"sent_at": None}, session=self._session)
        oldest = await self._outbox.find_one(
            {"sent_at": None}, sort=[("created_at", ASCENDING)], session=self._session
        )
        return OutboxBacklog(waiting, oldest["created_at"] if oldest else None)


async def prepare(database: Database) -> None:
    """Create the indexes the adapter relies on; safe to repeat."""
    await database["campaigns"].create_index("keitaro_id", unique=True)
    await database["campaigns"].create_index([("created_at", DESCENDING)])
    await database["streams"].create_index("keitaro_id", unique=True)
    await database["streams"].create_index([("campaign_id", ASCENDING), ("position", ASCENDING)])
    await database["audit_log"].create_index([("created_at", DESCENDING)])
    await database["tasks"].create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    await database["tasks"].create_index([("created_at", DESCENDING)])
    await database["outbox"].create_index([("sent_at", ASCENDING), ("created_at", ASCENDING)])


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
                        tasks=MongoTasks(database, session),
                        outbox=MongoOutbox(database, session),
                    )

    return Storage(
        campaigns=MongoCampaigns(database),
        streams=MongoStreams(database),
        audit=MongoAudit(database),
        tasks=MongoTasks(database),
        outbox=MongoOutbox(database),
        transaction=transaction,
    )
