"""Publication of a stream as a task (R-ED-20…26, R-TK-04, 05, R-EV-07…09)."""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from app.keitaro.models import StreamOffer
from app.messaging.ports import Message
from app.services.catalog import CatalogService
from app.services.editor import EditorService
from app.services.errors import (
    DomainError,
    EmptyStreamError,
    StreamBusyError,
    StreamConflictError,
    StreamNotFoundError,
    TaskKeyReusedError,
)
from app.services.models import AuditEntry, OfferLink, Published, Stream, Task, TaskStatus
from app.services.publisher import (
    PUBLISH_REJECTED,
    PUBLISH_REQUESTED,
    PUBLISHED,
    PublisherService,
)
from app.services.shares import OfferState
from app.storage.memory import create_memory_storage
from app.storage.ports import Storage
from tests.fakes import (
    CAMPAIGN_ID,
    OFFERS_STREAM_ID,
    A,
    B,
    C,
    D,
    FakeKeitaro,
    tracker_with_campaign,
)
from tests.graphql.support import NOW

pytestmark = pytest.mark.anyio

REMOVED = OfferState.REMOVED
MAX_ATTEMPTS = 3
SEND = "replace_stream_offers"


@pytest.fixture
def keitaro() -> FakeKeitaro:
    return tracker_with_campaign()


@pytest.fixture
def storage() -> Storage:
    return create_memory_storage()


@pytest.fixture
def editor(keitaro: FakeKeitaro, storage: Storage) -> EditorService:
    return EditorService(keitaro, CatalogService(keitaro), storage, clock=lambda: NOW)


@pytest.fixture
def publisher(keitaro: FakeKeitaro, storage: Storage) -> PublisherService:
    return PublisherService(keitaro, storage, clock=lambda: NOW, max_attempts=MAX_ATTEMPTS)


@pytest.fixture
async def stream(editor: EditorService) -> Stream:
    """Scenario S1: A 34, B 33, C 33, nothing pending."""
    fetched = await editor.fetch(CAMPAIGN_ID)
    return fetched.streams[1]


def in_tracker(keitaro: FakeKeitaro) -> list[tuple[int, int]]:
    return [(offer.offer_id, offer.share) for offer in keitaro.streams[OFFERS_STREAM_ID].offers]


def delivery(task: Task, attempt: int = 1) -> Message:
    return Message(uuid4(), PUBLISH_REQUESTED, {"task_id": str(task.id)}, attempt)


async def publish(publisher: PublisherService, stream_id: UUID) -> Task:
    """Queue the publication and let the worker do it at once."""
    task = await publisher.request(stream_id, uuid4())
    await publisher.handle(delivery(task))
    return await stored(publisher, task)


async def stored(publisher: PublisherService, task: Task) -> Task:
    found = await publisher.task(task.id)
    assert found is not None
    return found


async def the_stream(storage: Storage, stream: Stream) -> Stream:
    found = await storage.streams.get(stream.id)
    assert found is not None
    return found


async def topics(storage: Storage) -> list[str]:
    waiting = await storage.outbox.claim(limit=50, now=NOW, lease=NOW - NOW)
    return [message.topic for message in waiting]


async def last_publication(storage: Storage) -> AuditEntry:
    entries = await storage.audit.list_recent()
    return next(entry for entry in entries if entry.action.startswith("stream.push"))


async def test_request_queues_a_task_and_touches_nothing_else(
    editor: EditorService,
    publisher: PublisherService,
    keitaro: FakeKeitaro,
    storage: Storage,
    stream: Stream,
) -> None:
    """R-ED-20, R-ED-25, R-EV-01: the tracker is written by the worker, not by the request."""
    draft = await editor.add_offer(stream.id, D)

    task = await publisher.request(stream.id, uuid4(), expected=draft.version)

    busy = await the_stream(storage, stream)
    assert (task.status, task.attempts, task.stream_id) == (TaskStatus.PENDING, 0, stream.id)
    assert task.campaign_id == stream.campaign_id
    assert task.payload["after"] == [{"offer_id": offer, "share": 25} for offer in (A, B, C, D)]
    assert await stored(publisher, task) == task
    assert (busy.publishing, busy.dirty, busy.offers) == (task.id, True, draft.offers)
    assert in_tracker(keitaro) == [(A, 34), (B, 33), (C, 33)]
    assert await topics(storage) == [PUBLISH_REQUESTED]


async def test_s3_draft_goes_to_the_tracker(
    editor: EditorService,
    publisher: PublisherService,
    keitaro: FakeKeitaro,
    storage: Storage,
    stream: Stream,
) -> None:
    """S3, R-ED-20, R-ED-21, R-EV-09."""
    await editor.add_offer(stream.id, D)

    task = await publish(publisher, stream.id)

    after = await the_stream(storage, stream)
    assert (task.status, task.attempts, task.refusal) == (TaskStatus.SUCCEEDED, 1, None)
    assert (task.started_at, task.finished_at) == (NOW, NOW)
    assert [step.name for step in task.steps] == ["queued", "attempt", "published"]
    assert in_tracker(keitaro) == [(A, 25), (B, 25), (C, 25), (D, 25)]
    assert (after.dirty, after.publishing) == (False, None)
    assert after.offers[3] == OfferLink(D, "Offer D", 25, published=Published(25))
    assert await topics(storage) == [PUBLISH_REQUESTED, PUBLISHED]


async def test_s5_removed_offer_leaves_the_tracker_and_can_return(
    editor: EditorService,
    publisher: PublisherService,
    keitaro: FakeKeitaro,
    storage: Storage,
    stream: Stream,
) -> None:
    """S5, R-ED-20, R-ED-21."""
    await editor.add_offer(stream.id, D)
    await publish(publisher, stream.id)

    await editor.remove_offer(stream.id, B)
    await publish(publisher, stream.id)
    published = await the_stream(storage, stream)
    assert in_tracker(keitaro) == [(A, 34), (C, 33), (D, 33)]
    assert published.offers[1] == OfferLink(
        B, "Offer B", 0, state=REMOVED, published=Published(0, REMOVED)
    )

    await editor.bring_back(stream.id, B)
    await publish(publisher, stream.id)
    assert sorted(in_tracker(keitaro)) == [(A, 25), (B, 25), (C, 25), (D, 25)]


async def test_only_what_the_tracker_needs_is_sent(
    editor: EditorService, publisher: PublisherService, keitaro: FakeKeitaro, stream: Stream
) -> None:
    """R-ED-20: active offers in our order, each with its share."""
    await editor.remove_offer(stream.id, A)
    await editor.add_offer(stream.id, D)

    await publish(publisher, stream.id)

    assert keitaro.streams[OFFERS_STREAM_ID].offers == (
        StreamOffer(offer_id=B, share=34),
        StreamOffer(offer_id=C, share=33),
        StreamOffer(offer_id=D, share=33),
    )
    assert keitaro.calls[SEND] == 1


async def test_pin_becomes_part_of_the_published_snapshot(
    editor: EditorService, publisher: PublisherService, storage: Storage, stream: Stream
) -> None:
    """R-ED-21, R-ED-14: a later cancel keeps the pin that was published."""
    await editor.pin_share(stream.id, C, 25)
    await publish(publisher, stream.id)
    published = await the_stream(storage, stream)
    await editor.add_offer(stream.id, D)

    cancelled = await editor.cancel(stream.id)

    assert published.offers[2].published == Published(25, pinned=True)
    assert cancelled == published


async def test_refusal_of_the_tracker_rejects_the_task_and_keeps_the_draft(
    editor: EditorService,
    publisher: PublisherService,
    keitaro: FakeKeitaro,
    storage: Storage,
    stream: Stream,
) -> None:
    """R-ED-22, R-EV-08, R-EV-09: a 4xx is final at the first attempt."""
    draft = await editor.add_offer(stream.id, D)
    keitaro.fail_on.add(SEND)
    keitaro.fail_status = 422

    task = await publish(publisher, stream.id)

    after = await the_stream(storage, stream)
    assert (task.status, task.attempts) == (TaskStatus.REJECTED, 1)
    assert task.refusal is not None
    assert (task.refusal.code, task.refusal.message) == (
        "keitaro_error",
        "Keitaro: replace_stream_offers failed",
    )
    assert (after.offers, after.dirty, after.publishing) == (draft.offers, True, None)
    assert in_tracker(keitaro) == [(A, 34), (B, 33), (C, 33)]
    assert await topics(storage) == [PUBLISH_REQUESTED, PUBLISH_REJECTED]


@pytest.mark.parametrize("status", [500, None])
async def test_passing_failure_asks_for_another_delivery(  # noqa: PLR0913, PLR0917 — fixtures and a parameter
    editor: EditorService,
    publisher: PublisherService,
    keitaro: FakeKeitaro,
    storage: Storage,
    stream: Stream,
    status: int | None,
) -> None:
    """R-EV-08: a 5xx or no answer at all is worth another attempt."""
    await editor.add_offer(stream.id, D)
    task = await publisher.request(stream.id, uuid4())
    keitaro.fail_on.add(SEND)
    keitaro.fail_status = status

    with pytest.raises(DomainError):
        await publisher.handle(delivery(task, attempt=1))
    waiting = await stored(publisher, task)
    keitaro.fail_on.clear()
    await publisher.handle(delivery(task, attempt=2))

    done = await stored(publisher, task)
    assert (waiting.status, waiting.attempts) == (TaskStatus.RUNNING, 1)
    assert (await the_stream(storage, stream)).publishing is None
    assert (done.status, done.attempts) == (TaskStatus.SUCCEEDED, 2)
    assert in_tracker(keitaro) == [(A, 25), (B, 25), (C, 25), (D, 25)]


async def test_last_attempt_rejects_the_task(
    editor: EditorService,
    publisher: PublisherService,
    keitaro: FakeKeitaro,
    storage: Storage,
    stream: Stream,
) -> None:
    """R-EV-08."""
    await editor.add_offer(stream.id, D)
    task = await publisher.request(stream.id, uuid4())
    keitaro.fail_on.add(SEND)

    await publisher.handle(delivery(task, attempt=MAX_ATTEMPTS))

    done = await stored(publisher, task)
    assert done.status is TaskStatus.REJECTED
    assert (await the_stream(storage, stream)).dirty


async def test_dead_letter_rejects_a_task_nobody_handled(
    editor: EditorService, publisher: PublisherService, storage: Storage, stream: Stream
) -> None:
    """R-EV-08: the task does not hang, the stream is free again."""
    draft = await editor.add_offer(stream.id, D)
    task = await publisher.request(stream.id, uuid4())

    await publisher.bury(delivery(task))
    await publisher.bury(delivery(task))

    done = await stored(publisher, task)
    after = await the_stream(storage, stream)
    assert done.status is TaskStatus.REJECTED
    assert done.refusal is not None
    assert done.refusal.code == "attempts_exhausted"
    assert (after.offers, after.publishing) == (draft.offers, None)
    assert await topics(storage) == [PUBLISH_REQUESTED, PUBLISH_REJECTED]


async def test_repeated_delivery_of_a_finished_task_does_nothing(
    editor: EditorService,
    publisher: PublisherService,
    keitaro: FakeKeitaro,
    storage: Storage,
    stream: Stream,
) -> None:
    """R-EV-07."""
    await editor.add_offer(stream.id, D)
    task = await publish(publisher, stream.id)
    after = await the_stream(storage, stream)

    await publisher.handle(delivery(task, attempt=2))
    await publisher.handle(Message(uuid4(), PUBLISH_REQUESTED, {"task_id": str(uuid4())}))

    assert await stored(publisher, task) == task
    assert await the_stream(storage, stream) == after
    assert keitaro.calls[SEND] == 1
    assert await topics(storage) == [PUBLISH_REQUESTED, PUBLISHED]


async def test_delivery_after_a_lost_answer_ends_the_same_way(
    editor: EditorService,
    publisher: PublisherService,
    keitaro: FakeKeitaro,
    storage: Storage,
    stream: Stream,
) -> None:
    """R-EV-07: the tracker applied the change, the answer was lost, the message came again."""
    await editor.add_offer(stream.id, D)
    task = await publisher.request(stream.id, uuid4())
    keitaro.lose_answer.add(SEND)

    with pytest.raises(DomainError):
        await publisher.handle(delivery(task, attempt=1))
    keitaro.lose_answer.clear()
    await publisher.handle(delivery(task, attempt=2))

    after = await the_stream(storage, stream)
    assert (await stored(publisher, task)).status is TaskStatus.SUCCEEDED
    assert in_tracker(keitaro) == [(A, 25), (B, 25), (C, 25), (D, 25)]
    assert (after.dirty, after.publishing) == (False, None)


async def test_same_task_id_again_answers_with_the_same_task(
    editor: EditorService,
    publisher: PublisherService,
    keitaro: FakeKeitaro,
    storage: Storage,
    stream: Stream,
) -> None:
    """R-TK-04: a repeat neither queues nor publishes anything twice."""
    await editor.add_offer(stream.id, D)
    task_id = uuid4()

    first = await publisher.request(stream.id, task_id)
    again = await publisher.request(stream.id, task_id)
    await publisher.handle(delivery(first))
    after_the_end = await publisher.request(stream.id, task_id)

    assert again == first
    assert after_the_end.status is TaskStatus.SUCCEEDED
    assert keitaro.calls[SEND] == 1
    assert await topics(storage) == [PUBLISH_REQUESTED, PUBLISHED]


async def test_task_id_of_another_request_is_refused(
    editor: EditorService, publisher: PublisherService, stream: Stream
) -> None:
    """R-TK-04."""
    await editor.add_offer(stream.id, D)
    task = await publisher.request(stream.id, uuid4())

    with pytest.raises(TaskKeyReusedError):
        await publisher.request(uuid4(), task.id)


async def test_busy_stream_is_not_edited_cancelled_published_or_reloaded(
    editor: EditorService,
    publisher: PublisherService,
    keitaro: FakeKeitaro,
    storage: Storage,
    stream: Stream,
) -> None:
    """R-ED-25."""
    draft = await editor.add_offer(stream.id, D)
    task = await publisher.request(stream.id, uuid4())
    busy = await the_stream(storage, stream)

    for action in (
        editor.remove_offer(stream.id, A),
        editor.pin_share(stream.id, A, 50),
        editor.cancel(stream.id),
        editor.fetch(CAMPAIGN_ID),
        publisher.request(stream.id, uuid4()),
    ):
        with pytest.raises(StreamBusyError, match="Flow 2"):
            await action

    assert await the_stream(storage, stream) == busy
    assert busy.offers == draft.offers
    await publisher.handle(delivery(task))
    assert (await editor.remove_offer(stream.id, A)).dirty
    assert keitaro.calls[SEND] == 1


async def test_stream_without_active_offers_is_not_queued(
    editor: EditorService,
    publisher: PublisherService,
    storage: Storage,
    stream: Stream,
) -> None:
    """R-ED-23."""
    for offer_id in (A, B, C):
        await editor.remove_offer(stream.id, offer_id)
    task_id = uuid4()

    with pytest.raises(EmptyStreamError, match="Flow 2"):
        await publisher.request(stream.id, task_id)

    assert await publisher.task(task_id) is None
    assert await topics(storage) == []


async def test_clean_stream_is_done_without_the_tracker(
    publisher: PublisherService, keitaro: FakeKeitaro, storage: Storage, stream: Stream
) -> None:
    """R-ED-26."""
    task = await publisher.request(stream.id, uuid4())

    assert (task.status, task.finished_at) == (TaskStatus.SUCCEEDED, NOW)
    assert await stored(publisher, task) == task
    assert (await the_stream(storage, stream)).publishing is None
    assert keitaro.calls[SEND] == 0
    assert await topics(storage) == []


async def test_outdated_or_unknown_stream_is_refused(
    editor: EditorService, publisher: PublisherService, storage: Storage, stream: Stream
) -> None:
    """R-CC-06."""
    current = await editor.add_offer(stream.id, D)

    with pytest.raises(StreamConflictError) as refusal:
        await publisher.request(stream.id, uuid4(), expected=stream.version)
    with pytest.raises(StreamNotFoundError):
        await publisher.request(uuid4(), uuid4())

    assert refusal.value.current == current
    assert await the_stream(storage, stream) == replace(current, publishing=None)


@pytest.mark.parametrize("fails", [False, True])
async def test_publication_is_journaled_with_before_and_after(  # noqa: PLR0913 — fixtures and a parameter
    editor: EditorService,
    publisher: PublisherService,
    keitaro: FakeKeitaro,
    storage: Storage,
    stream: Stream,
    *,
    fails: bool,
) -> None:
    """R-ED-24."""
    await editor.remove_offer(stream.id, C)
    await editor.add_offer(stream.id, D)
    if fails:
        keitaro.fail_on.add(SEND)
        keitaro.fail_status = 400

    await publish(publisher, stream.id)

    entry = await last_publication(storage)
    assert (entry.action, entry.stream_id, entry.campaign_id) == (
        "stream.push_failed" if fails else "stream.pushed",
        stream.id,
        stream.campaign_id,
    )
    assert entry.details["before"] == [
        {"offer_id": A, "share": 34},
        {"offer_id": B, "share": 33},
        {"offer_id": C, "share": 33},
    ]
    assert entry.details["after"] == [
        {"offer_id": A, "share": 34},
        {"offer_id": B, "share": 33},
        {"offer_id": D, "share": 33},
    ]
    assert entry.details.get("error") == (
        "Keitaro: replace_stream_offers failed" if fails else None
    )
