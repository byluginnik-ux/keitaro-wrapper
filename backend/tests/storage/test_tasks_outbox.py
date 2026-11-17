"""Tasks and the outbox, one contract for every storage adapter (R-TK-01…03, R-EV-01, 02)."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.services.models import (
    OutboxBacklog,
    OutboxMessage,
    Refusal,
    Task,
    TaskKind,
    TaskStatus,
    TaskStep,
)
from app.storage.errors import DuplicateError, StaleTaskError, StorageConflictError
from app.storage.ports import Storage

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
LEASE = timedelta(seconds=30)
PENDING, RUNNING, SUCCEEDED, REJECTED, CANCELLED = (
    TaskStatus.PENDING,
    TaskStatus.RUNNING,
    TaskStatus.SUCCEEDED,
    TaskStatus.REJECTED,
    TaskStatus.CANCELLED,
)


def task(*, minutes: int = 0, kind: TaskKind = TaskKind.PUBLISH_STREAM) -> Task:
    return Task(
        id=uuid4(),
        kind=kind,
        created_at=NOW + timedelta(minutes=minutes),
        fingerprint="f" * 64,
        payload={"offers": [{"offer_id": 11111, "share": 100}], "keitaro_id": 564221},
        campaign_id=uuid4(),
        stream_id=uuid4(),
    )


def message(*, seconds: int = 0, topic: str = "stream.publish.requested") -> OutboxMessage:
    return OutboxMessage(
        uuid4(), topic, NOW + timedelta(seconds=seconds), {"task_id": str(uuid4())}
    )


def ids(messages: list[OutboxMessage]) -> list[UUID]:
    return [item.id for item in messages]


async def test_task_round_trips_with_everything_it_carries(storage: Storage) -> None:
    """R-TK-01."""
    new = task()
    done = replace(
        new,
        status=REJECTED,
        attempts=3,
        started_at=NOW + timedelta(seconds=1),
        finished_at=NOW + timedelta(seconds=9),
        refusal=Refusal("keitaro_error", "Keitaro не ответил", {"share": "мало"}, {"status": 502}),
        steps=(
            TaskStep("started", NOW + timedelta(seconds=1)),
            TaskStep("tracker", NOW + timedelta(seconds=9), "HTTP 502"),
        ),
        retry_of=uuid4(),
    )

    await storage.tasks.add(new)
    assert await storage.tasks.get(new.id) == new
    await storage.tasks.save(done, was=PENDING)

    assert await storage.tasks.get(new.id) == done
    assert await storage.tasks.get(uuid4()) is None


async def test_second_task_with_the_same_id_is_refused(storage: Storage) -> None:
    """R-TK-03: the ID is the idempotency key."""
    first = task()
    await storage.tasks.add(first)

    with pytest.raises(DuplicateError):
        await storage.tasks.add(replace(first, payload={"other": True}))

    assert await storage.tasks.get(first.id) == first


async def test_transition_from_another_status_is_refused(storage: Storage) -> None:
    """R-TK-02."""
    stored = task()
    await storage.tasks.add(stored)
    await storage.tasks.save(replace(stored, status=CANCELLED), was=PENDING)

    with pytest.raises(StaleTaskError):
        await storage.tasks.save(replace(stored, status=RUNNING), was=PENDING)
    with pytest.raises(StaleTaskError):
        await storage.tasks.save(task(), was=PENDING)

    loaded = await storage.tasks.get(stored.id)
    assert loaded is not None
    assert loaded.status is CANCELLED


async def test_one_of_two_simultaneous_transitions_wins(storage: Storage) -> None:
    """R-TK-02: the worker takes the task while the user cancels it."""
    stored = task()
    await storage.tasks.add(stored)

    results = await asyncio.gather(
        storage.tasks.save(replace(stored, status=RUNNING), was=PENDING),
        storage.tasks.save(replace(stored, status=CANCELLED), was=PENDING),
        return_exceptions=True,
    )

    refused = [item for item in results if isinstance(item, BaseException)]
    loaded = await storage.tasks.get(stored.id)
    assert len(refused) == 1
    assert isinstance(refused[0], StorageConflictError)
    assert loaded is not None
    assert loaded.status in {RUNNING, CANCELLED}


async def test_tasks_are_listed_newest_first_and_filtered(storage: Storage) -> None:
    """R-TK-01."""
    old, middle, new = (
        task(minutes=0),
        task(minutes=1, kind=TaskKind.CREATE_CAMPAIGN),
        task(minutes=2),
    )
    for item in (old, middle, new):
        await storage.tasks.add(item)
    failed = replace(old, status=REJECTED)
    await storage.tasks.save(failed, was=PENDING)

    assert await storage.tasks.list_recent() == [new, middle, failed]
    assert await storage.tasks.list_recent(limit=2) == [new, middle]
    assert await storage.tasks.list_recent(before=middle.created_at) == [failed]
    assert await storage.tasks.list_recent(statuses=[PENDING]) == [new, middle]
    assert await storage.tasks.list_recent(statuses=[REJECTED, SUCCEEDED]) == [failed]
    assert await storage.tasks.list_recent(kind=TaskKind.CREATE_CAMPAIGN) == [middle]
    assert await storage.tasks.count_by_status() == {PENDING: 2, REJECTED: 1}


async def test_task_and_its_message_are_written_together_or_not_at_all(storage: Storage) -> None:
    """R-EV-01."""
    kept, lost = task(), task()
    announced = message()

    async with storage.transaction() as work:
        await work.tasks.add(kept)
        await work.outbox.put(announced)

    async def fail_midway() -> None:
        async with storage.transaction() as work:
            await work.tasks.add(lost)
            await work.outbox.put(message(seconds=1))
            raise RuntimeError

    with pytest.raises(RuntimeError):
        await fail_midway()

    assert await storage.tasks.get(kept.id) == kept
    assert await storage.tasks.get(lost.id) is None
    assert await storage.outbox.claim(limit=10, now=NOW, lease=LEASE) == [announced]


async def test_messages_are_claimed_oldest_first_and_only_once(storage: Storage) -> None:
    """R-EV-02."""
    third, first, second = message(seconds=3), message(seconds=1), message(seconds=2)
    for item in (third, first, second):
        await storage.outbox.put(item)

    batch = await storage.outbox.claim(limit=2, now=NOW, lease=LEASE)
    rest = await storage.outbox.claim(limit=2, now=NOW, lease=LEASE)
    nothing = await storage.outbox.claim(limit=2, now=NOW, lease=LEASE)

    assert (batch, rest, nothing) == ([first, second], [third], [])


async def test_two_senders_never_take_the_same_message(storage: Storage) -> None:
    """R-EV-02."""
    queued = [message(seconds=second) for second in range(20)]
    for item in queued:
        await storage.outbox.put(item)

    batches = await asyncio.gather(
        *(storage.outbox.claim(limit=5, now=NOW, lease=LEASE) for _ in range(4))
    )

    taken = [item.id for batch in batches for item in batch]
    assert len(taken) == len(set(taken))
    assert set(taken) == set(ids(queued))


async def test_expired_claim_is_given_again_and_sent_message_never(storage: Storage) -> None:
    """R-EV-02: the sender died after taking the first message and delivered the second."""
    abandoned, delivered = message(seconds=1), message(seconds=2)
    await storage.outbox.put(abandoned)
    await storage.outbox.put(delivered)
    await storage.outbox.claim(limit=2, now=NOW, lease=LEASE)
    await storage.outbox.mark_sent([delivered.id], NOW)

    early = await storage.outbox.claim(limit=2, now=NOW + LEASE / 2, lease=LEASE)
    later = await storage.outbox.claim(limit=2, now=NOW + LEASE, lease=LEASE)

    assert (early, later) == ([], [abandoned])
    assert await storage.outbox.backlog() == OutboxBacklog(1, abandoned.created_at)
    await storage.outbox.mark_sent([abandoned.id], NOW + LEASE)
    assert await storage.outbox.backlog() == OutboxBacklog(0, None)
