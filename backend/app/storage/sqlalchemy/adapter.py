from collections.abc import AsyncGenerator, Callable, Collection, Generator, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager, contextmanager
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

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
)
from app.storage.ports import Storage, UnitOfWork
from app.storage.sqlalchemy.tables import (
    AuditRow,
    CampaignRow,
    OutboxRow,
    StreamOfferRow,
    StreamRow,
    TaskRow,
)

type Scope = Callable[[], AbstractAsyncContextManager[AsyncSession]]
"""Where a repository gets its session: a transaction of its own or a shared one."""

FOREIGN_KEY_VIOLATION = "23503"


@contextmanager
def _integrity() -> Generator[None]:
    """Tell a missing campaign from a record that is already there (R-ST-06)."""
    try:
        yield
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) == FOREIGN_KEY_VIOLATION:
            message = "a stream refers to a campaign that is not stored"
            raise MissingParentError(message) from error
        message = "a record with the same identity is already stored"
        raise DuplicateError(message) from error


def _campaign(row: CampaignRow) -> Campaign:
    return Campaign(
        id=row.id,
        keitaro_id=row.keitaro_id,
        name=row.name,
        alias=row.alias,
        created_at=row.created_at,
        country=row.country,
        domain_id=row.domain_id,
        group_id=row.group_id,
        traffic_source_id=row.traffic_source_id,
    )


def _offer(row: StreamOfferRow) -> OfferLink:
    published = None
    if row.published_share is not None:
        published = Published(
            share=row.published_share,
            state=OfferState(row.published_state or OfferState.ACTIVE),
            pinned=bool(row.published_pinned),
        )
    return OfferLink(
        offer_id=row.offer_id,
        name=row.name,
        share=row.share,
        pinned=row.pinned,
        state=OfferState(row.state),
        published=published,
    )


def _stream(row: StreamRow) -> Stream:
    return Stream(
        id=row.id,
        campaign_id=row.campaign_id,
        keitaro_id=row.keitaro_id,
        name=row.name,
        position=row.position,
        kind=row.kind,
        offers=tuple(_offer(offer) for offer in row.offers),
        version=row.version,
        publishing=row.publishing_task_id,
    )


def _stream_values(stream: Stream) -> dict[str, Any]:
    return {
        "campaign_id": stream.campaign_id,
        "keitaro_id": stream.keitaro_id,
        "name": stream.name,
        "position": stream.position,
        "kind": stream.kind,
        "version": stream.version + 1,
        "publishing_task_id": stream.publishing,
    }


def _offer_values(stream_id: UUID, position: int, link: OfferLink) -> dict[str, Any]:
    published = link.published
    return {
        "stream_id": stream_id,
        "offer_id": link.offer_id,
        "position": position,
        "name": link.name,
        "share": link.share,
        "pinned": link.pinned,
        "state": link.state.value,
        "published_share": published.share if published else None,
        "published_state": published.state.value if published else None,
        "published_pinned": published.pinned if published else None,
    }


class SqlCampaigns:
    def __init__(self, scope: Scope) -> None:
        self._scope = scope

    async def add(self, campaign: Campaign) -> None:
        async with self._scope() as session:
            with _integrity():
                await session.execute(
                    insert(CampaignRow).values(
                        id=campaign.id,
                        keitaro_id=campaign.keitaro_id,
                        name=campaign.name,
                        alias=campaign.alias,
                        created_at=campaign.created_at,
                        country=campaign.country,
                        domain_id=campaign.domain_id,
                        group_id=campaign.group_id,
                        traffic_source_id=campaign.traffic_source_id,
                    )
                )

    async def get(self, campaign_id: UUID) -> Campaign | None:
        async with self._scope() as session:
            row = await session.get(CampaignRow, campaign_id, populate_existing=True)
            return _campaign(row) if row else None

    async def get_by_keitaro_id(self, keitaro_id: int) -> Campaign | None:
        async with self._scope() as session:
            query = select(CampaignRow).where(CampaignRow.keitaro_id == keitaro_id)
            row = await session.scalar(query)
            return _campaign(row) if row else None

    async def list_recent(self) -> list[Campaign]:
        async with self._scope() as session:
            rows = await session.scalars(
                select(CampaignRow).order_by(CampaignRow.created_at.desc())
            )
            return [_campaign(row) for row in rows]


class SqlStreams:
    def __init__(self, scope: Scope) -> None:
        self._scope = scope

    async def get(self, stream_id: UUID) -> Stream | None:
        async with self._scope() as session:
            row = await session.get(StreamRow, stream_id, populate_existing=True)
            return _stream(row) if row else None

    async def list_by_campaign(self, campaign_id: UUID) -> list[Stream]:
        async with self._scope() as session:
            query = (
                select(StreamRow)
                .where(StreamRow.campaign_id == campaign_id)
                .order_by(StreamRow.position)
                .execution_options(populate_existing=True)
            )
            return [_stream(row) for row in await session.scalars(query)]

    async def save(self, stream: Stream) -> Stream:
        return (await self.save_all([stream]))[0]

    async def save_all(self, streams: Sequence[Stream]) -> list[Stream]:
        """Write every stream in one transaction; any refusal rolls all of it back.

        The conditional UPDATE takes the row lock: a concurrent writer waits for it
        and then finds another version (R-CC-02). Streams go in the order of their
        IDs, so two batches never wait for each other.
        """
        async with self._scope() as session:
            for stream in sorted(streams, key=lambda item: item.id):
                with _integrity():
                    await self._write(session, stream)
            session.expire_all()
        return [replace(stream, version=stream.version + 1) for stream in streams]

    @staticmethod
    async def _write(session: AsyncSession, stream: Stream) -> None:
        if stream.version == 0:
            await session.execute(insert(StreamRow).values(id=stream.id, **_stream_values(stream)))
        else:
            changed = await session.execute(
                update(StreamRow)
                .where(StreamRow.id == stream.id, StreamRow.version == stream.version)
                .values(**_stream_values(stream))
            )
            if cast("CursorResult[Any]", changed).rowcount != 1:
                raise StaleStreamError(stream.id)
            await session.execute(
                delete(StreamOfferRow).where(StreamOfferRow.stream_id == stream.id)
            )
        if stream.offers:
            await session.execute(
                insert(StreamOfferRow),
                [
                    _offer_values(stream.id, position, link)
                    for position, link in enumerate(stream.offers)
                ],
            )

    async def delete(self, stream_id: UUID) -> None:
        async with self._scope() as session:
            await session.execute(delete(StreamRow).where(StreamRow.id == stream_id))
            session.expire_all()


class SqlAudit:
    def __init__(self, scope: Scope) -> None:
        self._scope = scope

    async def record(self, entry: AuditEntry) -> None:
        async with self._scope() as session:
            await session.execute(
                insert(AuditRow).values(
                    id=entry.id,
                    action=entry.action,
                    created_at=entry.created_at,
                    campaign_id=entry.campaign_id,
                    stream_id=entry.stream_id,
                    details=dict(entry.details),
                )
            )

    async def list_recent(self, limit: int = 50) -> list[AuditEntry]:
        async with self._scope() as session:
            query = select(AuditRow).order_by(AuditRow.created_at.desc()).limit(limit)
            return [
                AuditEntry(
                    id=row.id,
                    action=row.action,
                    created_at=row.created_at,
                    campaign_id=row.campaign_id,
                    stream_id=row.stream_id,
                    details=row.details,
                )
                for row in await session.scalars(query)
            ]


def _task(row: TaskRow) -> Task:
    return Task(
        id=row.id,
        kind=TaskKind(row.kind),
        created_at=row.created_at,
        fingerprint=row.fingerprint,
        payload=row.payload,
        status=TaskStatus(row.status),
        attempts=row.attempts,
        campaign_id=row.campaign_id,
        stream_id=row.stream_id,
        started_at=row.started_at,
        finished_at=row.finished_at,
        refusal=codec.refusal_from_json(row.refusal),
        steps=codec.steps_from_json(row.steps),
        retry_of=row.retry_of,
    )


def _task_values(task: Task) -> dict[str, Any]:
    return {
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


class SqlTasks:
    def __init__(self, scope: Scope) -> None:
        self._scope = scope

    async def add(self, task: Task) -> None:
        async with self._scope() as session:
            with _integrity():
                await session.execute(insert(TaskRow).values(id=task.id, **_task_values(task)))

    async def get(self, task_id: UUID) -> Task | None:
        async with self._scope() as session:
            row = await session.get(TaskRow, task_id, populate_existing=True)
            return _task(row) if row else None

    async def save(self, task: Task, *, was: TaskStatus) -> None:
        """Let exactly one of two transitions through with a conditional UPDATE (R-TK-02)."""
        async with self._scope() as session:
            changed = await session.execute(
                update(TaskRow)
                .where(TaskRow.id == task.id, TaskRow.status == was.value)
                .values(**_task_values(task))
            )
            if cast("CursorResult[Any]", changed).rowcount != 1:
                raise StaleTaskError(task.id)
            session.expire_all()

    async def list_recent(
        self,
        *,
        statuses: Collection[TaskStatus] = (),
        kind: TaskKind | None = None,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[Task]:
        query = select(TaskRow).order_by(TaskRow.created_at.desc()).limit(limit)
        if statuses:
            query = query.where(TaskRow.status.in_([status.value for status in statuses]))
        if kind is not None:
            query = query.where(TaskRow.kind == kind.value)
        if before is not None:
            query = query.where(TaskRow.created_at < before)
        async with self._scope() as session:
            rows = await session.scalars(query.execution_options(populate_existing=True))
            return [_task(row) for row in rows]

    async def count_by_status(self) -> dict[TaskStatus, int]:
        async with self._scope() as session:
            rows = await session.execute(
                select(TaskRow.status, func.count()).group_by(TaskRow.status)
            )
            return {TaskStatus(status): count for status, count in rows}


class SqlOutbox:
    def __init__(self, scope: Scope) -> None:
        self._scope = scope

    async def put(self, message: OutboxMessage) -> None:
        async with self._scope() as session:
            await session.execute(
                insert(OutboxRow).values(
                    id=message.id,
                    topic=message.topic,
                    payload=dict(message.payload),
                    created_at=message.created_at,
                )
            )

    async def claim(self, *, limit: int, now: datetime, lease: timedelta) -> list[OutboxMessage]:
        """Take free rows with SKIP LOCKED: a second sender passes over them (R-EV-02)."""
        free = (
            select(OutboxRow.id)
            .where(
                OutboxRow.sent_at.is_(None),
                or_(OutboxRow.claimed_until.is_(None), OutboxRow.claimed_until <= now),
            )
            .order_by(OutboxRow.created_at, OutboxRow.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        async with self._scope() as session:
            taken = await session.execute(
                update(OutboxRow)
                .where(OutboxRow.id.in_(free))
                .values(claimed_until=now + lease)
                .returning(OutboxRow.id, OutboxRow.topic, OutboxRow.created_at, OutboxRow.payload)
            )
            messages = [
                OutboxMessage(
                    id=row.id, topic=row.topic, created_at=row.created_at, payload=row.payload
                )
                for row in taken
            ]
        return sorted(messages, key=lambda message: (message.created_at, message.id))

    async def mark_sent(self, ids: Sequence[UUID], now: datetime) -> None:
        if not ids:
            return
        async with self._scope() as session:
            await session.execute(
                update(OutboxRow).where(OutboxRow.id.in_(ids)).values(sent_at=now)
            )

    async def backlog(self) -> OutboxBacklog:
        async with self._scope() as session:
            row = (
                await session.execute(
                    select(func.count(), func.min(OutboxRow.created_at)).where(
                        OutboxRow.sent_at.is_(None)
                    )
                )
            ).one()
            return OutboxBacklog(waiting=row[0], oldest=row[1])


def create_sqlalchemy_storage(engine: AsyncEngine) -> Storage:
    """Persist through SQLAlchemy; the schema is owned by Alembic migrations (R-ST-02)."""
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def transaction() -> AsyncGenerator[UnitOfWork]:
        async with sessions.begin() as session:

            @asynccontextmanager
            async def joined() -> AsyncGenerator[AsyncSession]:
                yield session

            yield UnitOfWork(
                campaigns=SqlCampaigns(joined),
                streams=SqlStreams(joined),
                audit=SqlAudit(joined),
                tasks=SqlTasks(joined),
                outbox=SqlOutbox(joined),
            )

    return Storage(
        campaigns=SqlCampaigns(sessions.begin),
        streams=SqlStreams(sessions.begin),
        audit=SqlAudit(sessions.begin),
        tasks=SqlTasks(sessions.begin),
        outbox=SqlOutbox(sessions.begin),
        transaction=transaction,
    )
