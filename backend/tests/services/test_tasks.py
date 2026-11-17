"""Listing, cancelling and repeating tasks; the state of the queue (R-TK-06…09)."""

from uuid import uuid4

import pytest

from app.messaging.memory import MemoryBus
from app.messaging.ports import Message, QueueStats
from app.runtime import QUEUES, TASKS
from app.services.catalog import CatalogService
from app.services.creator import CREATE_REQUESTED, CreatorService, NewCampaignRequest
from app.services.editor import EditorService
from app.services.errors import (
    StreamBusyError,
    TaskNotCancellableError,
    TaskNotFoundError,
    TaskNotRetryableError,
    ValidationError,
)
from app.services.models import Stream, Task, TaskKind, TaskStatus
from app.services.publisher import PUBLISH_REQUESTED, PublisherService
from app.services.tasks import TasksService
from app.storage.memory import create_memory_storage
from app.storage.ports import Storage
from tests.fakes import CAMPAIGN_ID, OFFERS_STREAM_ID, D, FakeKeitaro, tracker_with_campaign
from tests.graphql.support import NOW, PREFIX

pytestmark = pytest.mark.anyio

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
    return PublisherService(keitaro, storage, clock=lambda: NOW)


@pytest.fixture
def tasks(storage: Storage, publisher: PublisherService) -> TasksService:
    bus = MemoryBus(QUEUES, max_attempts=3, retry_delay=0)
    return TasksService(
        storage, bus, publisher, creation(FakeKeitaro(), storage), clock=lambda: NOW
    )


@pytest.fixture
async def stream(editor: EditorService) -> Stream:
    """A stream with a draft: offer D is added and not published."""
    fetched = await editor.fetch(CAMPAIGN_ID)
    return await editor.add_offer(fetched.streams[1].id, D)


def delivery(task: Task) -> Message:
    return Message(uuid4(), PUBLISH_REQUESTED, {"task_id": str(task.id)}, 1)


async def rejected(publisher: PublisherService, keitaro: FakeKeitaro, stream: Stream) -> Task:
    keitaro.fail_on.add(SEND)
    keitaro.fail_status = 422
    task = await publisher.request(stream.id, uuid4())
    await publisher.handle(delivery(task))
    keitaro.fail_on.clear()
    done = await publisher.task(task.id)
    assert done is not None
    assert done.status is TaskStatus.REJECTED
    return done


async def test_tasks_are_listed_and_filtered(
    tasks: TasksService, publisher: PublisherService, keitaro: FakeKeitaro, stream: Stream
) -> None:
    """R-TK-06."""
    failed = await rejected(publisher, keitaro, stream)
    waiting = await publisher.request(stream.id, uuid4())

    everything = await tasks.recent()
    only_rejected = await tasks.recent(statuses=[TaskStatus.REJECTED])
    other_kind = await tasks.recent(kind=TaskKind.CREATE_CAMPAIGN)
    one = await tasks.recent(limit=0)

    assert {task.id for task in everything} == {failed.id, waiting.id}
    assert [task.id for task in only_rejected] == [failed.id]
    assert other_kind == []
    assert len(one) == 1


async def test_summary_counts_tasks_messages_and_listeners(
    tasks: TasksService, publisher: PublisherService, keitaro: FakeKeitaro, stream: Stream
) -> None:
    """R-TK-07."""
    await rejected(publisher, keitaro, stream)
    await publisher.request(stream.id, uuid4())

    summary = await tasks.summary()

    assert summary.tasks == {TaskStatus.REJECTED: 1, TaskStatus.PENDING: 1}
    assert (summary.outbox.waiting, summary.outbox.oldest) == (3, NOW)
    assert summary.queues == [QueueStats(TASKS.name, 0, 0), QueueStats(TASKS.dead, 0, 0)]


async def test_waiting_task_is_cancelled_and_the_stream_is_free(
    tasks: TasksService,
    publisher: PublisherService,
    keitaro: FakeKeitaro,
    storage: Storage,
    stream: Stream,
) -> None:
    """R-TK-08: the draft stays, the late message does nothing."""
    task = await publisher.request(stream.id, uuid4())

    cancelled = await tasks.cancel(task.id)
    await publisher.handle(delivery(task))

    after = await storage.streams.get(stream.id)
    assert after is not None
    assert (cancelled.status, cancelled.finished_at) == (TaskStatus.CANCELLED, NOW)
    assert cancelled.steps[-1].name == "cancelled"
    assert await publisher.task(task.id) == cancelled
    assert (after.publishing, after.dirty, after.offers) == (None, True, stream.offers)
    assert keitaro.calls[SEND] == 0


async def test_only_a_waiting_task_is_cancelled(
    tasks: TasksService, publisher: PublisherService, keitaro: FakeKeitaro, stream: Stream
) -> None:
    """R-TK-08."""
    done = await rejected(publisher, keitaro, stream)

    with pytest.raises(TaskNotCancellableError):
        await tasks.cancel(done.id)
    with pytest.raises(TaskNotFoundError):
        await tasks.cancel(uuid4())

    assert await publisher.task(done.id) == done


async def test_rejected_publication_is_repeated_as_a_new_task(
    tasks: TasksService, publisher: PublisherService, keitaro: FakeKeitaro, stream: Stream
) -> None:
    """R-TK-09."""
    failed = await rejected(publisher, keitaro, stream)
    new_id = uuid4()

    again = await tasks.retry(failed.id, new_id)
    same = await tasks.retry(failed.id, new_id)
    await publisher.handle(delivery(again))

    done = await publisher.task(new_id)
    assert done is not None
    assert (again.id, again.retry_of, again.status) == (new_id, failed.id, TaskStatus.PENDING)
    assert same == again
    assert done.status is TaskStatus.SUCCEEDED
    assert [offer.share for offer in keitaro.streams[OFFERS_STREAM_ID].offers] == [25] * 4
    assert await publisher.task(failed.id) == failed


async def test_what_cannot_be_repeated(
    tasks: TasksService, publisher: PublisherService, keitaro: FakeKeitaro, stream: Stream
) -> None:
    """R-TK-09."""
    failed = await rejected(publisher, keitaro, stream)
    waiting = await publisher.request(stream.id, uuid4())

    with pytest.raises(TaskNotRetryableError):
        await tasks.retry(waiting.id, uuid4())
    with pytest.raises(TaskNotFoundError):
        await tasks.retry(uuid4(), uuid4())
    with pytest.raises(StreamBusyError):
        await tasks.retry(failed.id, uuid4())


def creation(keitaro: FakeKeitaro, storage: Storage) -> CreatorService:
    return CreatorService(
        keitaro, CatalogService(keitaro), storage, name_prefix=PREFIX, clock=lambda: NOW
    )


NEW_CAMPAIGN = NewCampaignRequest(
    name="test_bulygin_again",
    country="AU",
    offer_id=D,
    group_id=10332,
    traffic_source_id=836,
    domain_id=1813,
)


async def test_rejected_creation_is_repeated_from_its_own_request(
    keitaro: FakeKeitaro, storage: Storage, publisher: PublisherService
) -> None:
    """R-TK-09: the request the task was queued with is checked and queued again."""
    creator = creation(keitaro, storage)
    tasks = TasksService(
        storage, MemoryBus(QUEUES, max_attempts=3, retry_delay=0), publisher, creator
    )
    keitaro.fail_on.add("create_stream")
    keitaro.fail_status = 400
    failed = await creator.request(NEW_CAMPAIGN, uuid4())
    await creator.handle(Message(uuid4(), CREATE_REQUESTED, {"task_id": str(failed.id)}, 1))
    keitaro.fail_on.clear()
    new_id = uuid4()

    again = await tasks.retry(failed.id, new_id)
    await creator.handle(Message(uuid4(), CREATE_REQUESTED, {"task_id": str(new_id)}, 1))

    done = await storage.tasks.get(new_id)
    assert done is not None
    assert (again.kind, again.retry_of, again.status) == (
        TaskKind.CREATE_CAMPAIGN,
        failed.id,
        TaskStatus.PENDING,
    )
    assert done.status is TaskStatus.SUCCEEDED
    assert [campaign.name for campaign in keitaro.campaigns.values()].count(
        "test_bulygin_again"
    ) == 1

    keitaro.groups.clear()
    with pytest.raises(ValidationError):
        await tasks.retry(failed.id, uuid4())


async def test_creation_queued_without_its_request_is_not_repeated(
    keitaro: FakeKeitaro, storage: Storage, publisher: PublisherService
) -> None:
    """R-TK-09: a task of an older version carries no request to repeat."""
    creator = creation(keitaro, storage)
    tasks = TasksService(
        storage, MemoryBus(QUEUES, max_attempts=3, retry_delay=0), publisher, creator
    )
    old = Task(
        id=uuid4(),
        kind=TaskKind.CREATE_CAMPAIGN,
        created_at=NOW,
        fingerprint="old",
        status=TaskStatus.REJECTED,
    )
    await storage.tasks.add(old)

    with pytest.raises(TaskNotRetryableError):
        await tasks.retry(old.id, uuid4())
