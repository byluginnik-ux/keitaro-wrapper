import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from uuid import UUID, uuid4

from app.keitaro import models as tracker
from app.keitaro.gateway import KeitaroGateway
from app.messaging.ports import Message
from app.services.creator import utc_now
from app.services.errors import (
    EmptyStreamError,
    KeitaroError,
    StreamBusyError,
    StreamConflictError,
    StreamNotFoundError,
    TaskKeyReusedError,
)
from app.services.models import (
    AuditEntry,
    OutboxMessage,
    Payload,
    Published,
    Refusal,
    Stream,
    Task,
    TaskKind,
    TaskStatus,
    TaskStep,
)
from app.services.shares import OfferState
from app.storage.errors import DuplicateError, StorageConflictError
from app.storage.ports import Storage

PUBLISH_REQUESTED = "stream.publish.requested"
PUBLISHED = "stream.published"
PUBLISH_REJECTED = "stream.publish.rejected"

SERVER_ERROR = 500


def _nothing() -> None:
    return None


def _fingerprint(stream_id: UUID) -> str:
    """Tell whether two requests with one task ID are the same request (R-TK-04)."""
    request = {"kind": TaskKind.PUBLISH_STREAM.value, "stream_id": str(stream_id)}
    return hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()


def _composition(stream: Stream) -> Payload:
    """Describe what the tracker holds now and what it must hold after the task (R-ED-20, 24)."""
    return {
        "keitaro_id": stream.keitaro_id,
        "before": [
            {"offer_id": link.offer_id, "share": link.published.share}
            for link in stream.offers
            if link.published is not None and link.published.state is OfferState.ACTIVE
        ],
        "after": [
            {"offer_id": link.offer_id, "share": link.share}
            for link in stream.offers
            if link.state is OfferState.ACTIVE
        ],
    }


class PublisherService:
    """Publish a stream as a task: queue it with the request, carry it out apart (R-ED-20…26)."""

    def __init__(
        self,
        keitaro: KeitaroGateway,
        storage: Storage,
        *,
        clock: Callable[[], datetime] = utc_now,
        max_attempts: int = 3,
        announce: Callable[[], None] = _nothing,
    ) -> None:
        self._keitaro = keitaro
        self._storage = storage
        self._clock = clock
        self._max_attempts = max_attempts
        self._announce = announce

    async def task(self, task_id: UUID) -> Task | None:
        return await self._storage.tasks.get(task_id)

    async def request(
        self,
        stream_id: UUID,
        task_id: UUID,
        *,
        expected: int | None = None,
        retry_of: UUID | None = None,
    ) -> Task:
        """Queue the publication; the same task ID again answers with the same task (R-TK-04)."""
        fingerprint = _fingerprint(stream_id)
        known = await self._storage.tasks.get(task_id)
        if known is not None:
            return _same(known, fingerprint)
        stream = await self._publishable(stream_id, expected)
        composition = _composition(stream)

        now = self._clock()
        task = Task(
            id=task_id,
            kind=TaskKind.PUBLISH_STREAM,
            created_at=now,
            fingerprint=fingerprint,
            payload=composition,
            campaign_id=stream.campaign_id,
            stream_id=stream.id,
            steps=(TaskStep("queued", now),),
            retry_of=retry_of,
        )
        if not stream.dirty:
            task = replace(
                task,
                status=TaskStatus.SUCCEEDED,
                finished_at=now,
                steps=(TaskStep("nothing to publish", now),),
            )
        try:
            async with self._storage.transaction() as work:
                await work.tasks.add(task)
                if not task.status.final:
                    await work.streams.save(replace(stream, publishing=task.id))
                    await work.outbox.put(
                        OutboxMessage(uuid4(), PUBLISH_REQUESTED, now, {"task_id": str(task.id)})
                    )
        except DuplicateError:
            raced = await self._storage.tasks.get(task_id)
            if raced is None:
                raise
            return _same(raced, fingerprint)
        except StorageConflictError as error:
            raise StreamConflictError(await self._storage.streams.get(stream_id)) from error
        self._announce()
        return task

    async def _publishable(self, stream_id: UUID, expected: int | None) -> Stream:
        """Read the stream and refuse what cannot be published (R-ED-23, 25, R-CC-06)."""
        stream = await self._storage.streams.get(stream_id)
        if stream is None:
            raise StreamNotFoundError
        if stream.publishing is not None:
            raise StreamBusyError(stream.name)
        if expected is not None and stream.version != expected:
            raise StreamConflictError(stream)
        if not any(link.state is OfferState.ACTIVE for link in stream.offers):
            raise EmptyStreamError(stream.name)
        return stream

    async def handle(self, message: Message) -> None:
        """Carry out a queued publication; any repeat of the message is harmless (R-EV-07).

        Raising asks the bus to deliver the message again later (R-EV-08).
        """
        task = await self._storage.tasks.get(UUID(message.payload["task_id"]))
        if task is None or task.status.final:
            return
        now = self._clock()
        running = replace(
            task,
            status=TaskStatus.RUNNING,
            attempts=task.attempts + 1,
            started_at=task.started_at or now,
            steps=(*task.steps, TaskStep("attempt", now, str(task.attempts + 1))),
        )
        try:
            await self._storage.tasks.save(running, was=task.status)
        except StorageConflictError:
            return  # cancelled or taken by another worker in between
        offers = [
            tracker.StreamOffer(offer_id=item["offer_id"], share=item["share"])
            for item in task.payload["after"]
        ]
        try:
            # replacing the whole composition twice gives the same result as once
            await self._keitaro.replace_stream_offers(task.payload["keitaro_id"], offers)
        except KeitaroError as error:
            transient = error.status is None or error.status >= SERVER_ERROR
            if transient and message.attempt < self._max_attempts:
                raise
            refusal = Refusal(error.code, str(error), details={"status": error.status})
            await self._finish(running, refusal)
            return
        await self._finish(running, None)

    async def bury(self, message: Message) -> None:
        """Close the task of a message nobody managed to handle (R-EV-08)."""
        task = await self._storage.tasks.get(UUID(message.payload["task_id"]))
        if task is None or task.status.final:
            return
        refusal = Refusal("attempts_exhausted", "Задачу не удалось выполнить: попытки исчерпаны")
        await self._finish(task, refusal)

    async def _finish(self, task: Task, refusal: Refusal | None) -> None:
        """Write the outcome, the journal and the final event together (R-ED-21…24, R-EV-09)."""
        now = self._clock()
        done = replace(
            task,
            status=TaskStatus.REJECTED if refusal else TaskStatus.SUCCEEDED,
            finished_at=now,
            refusal=refusal,
            steps=(*task.steps, TaskStep("rejected" if refusal else "published", now)),
        )
        details = {"before": task.payload["before"], "after": task.payload["after"]}
        if refusal:
            details["error"] = refusal.message
        try:
            async with self._storage.transaction() as work:
                await work.tasks.save(done, was=task.status)
                stream = await work.streams.get(task.stream_id) if task.stream_id else None
                if stream is not None and stream.publishing == task.id:
                    await work.streams.save(_released(stream, published=refusal is None))
                await work.audit.record(
                    AuditEntry(
                        id=uuid4(),
                        action="stream.push_failed" if refusal else "stream.pushed",
                        created_at=now,
                        campaign_id=task.campaign_id,
                        stream_id=task.stream_id,
                        details={"keitaro_id": task.payload["keitaro_id"], **details},
                    )
                )
                await work.outbox.put(
                    OutboxMessage(
                        uuid4(),
                        PUBLISH_REJECTED if refusal else PUBLISHED,
                        now,
                        {"task_id": str(task.id), "stream_id": str(task.stream_id)},
                    )
                )
        except StorageConflictError:
            return  # another delivery of the same message has already written the outcome
        self._announce()


def _same(known: Task, fingerprint: str) -> Task:
    if known.fingerprint != fingerprint:
        raise TaskKeyReusedError
    return known


def _released(stream: Stream, *, published: bool) -> Stream:
    """Free the stream; after a success the draft becomes the published snapshot (R-ED-21)."""
    if not published:
        return replace(stream, publishing=None)
    return replace(
        stream,
        publishing=None,
        offers=tuple(
            replace(link, published=Published(link.share, link.state, link.pinned))
            for link in stream.offers
        ),
    )
