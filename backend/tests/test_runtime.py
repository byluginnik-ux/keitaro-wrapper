"""The whole way of a publication: request → outbox → bus → worker (R-EV-03, 07, 08)."""

from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.messaging.memory import MemoryBus
from app.runtime import QUEUES, Runtime, assemble
from app.services.models import TaskStatus
from app.settings import Settings
from app.storage.memory import create_memory_storage
from tests.fakes import CAMPAIGN_ID, OFFERS_STREAM_ID, D, FakeKeitaro, tracker_with_campaign

pytestmark = pytest.mark.anyio

MAX_ATTEMPTS = 3


@pytest.fixture
def keitaro() -> FakeKeitaro:
    return tracker_with_campaign()


@pytest.fixture
async def runtime(keitaro: FakeKeitaro) -> Runtime:
    settings = Settings(keitaro_api_key=SecretStr("fake-key"), task_max_attempts=MAX_ATTEMPTS)
    bus = MemoryBus(QUEUES, max_attempts=MAX_ATTEMPTS, retry_delay=0)
    built = assemble(settings, keitaro, create_memory_storage(), bus)
    await built.consume_tasks()
    return built


async def settle(runtime: Runtime) -> None:
    """Send what waits in the outbox and let the handlers finish, retries included."""
    assert isinstance(runtime.bus, MemoryBus)
    while await runtime.relay.send_waiting():
        await runtime.bus.drain()
    await runtime.bus.drain()


async def queue_publication(runtime: Runtime) -> tuple[TaskStatus, int]:
    fetched = await runtime.editor.fetch(CAMPAIGN_ID)
    stream = fetched.streams[1]
    await runtime.editor.add_offer(stream.id, D)
    task = await runtime.publisher.request(stream.id, uuid4())
    await settle(runtime)
    done = await runtime.publisher.task(task.id)
    assert done is not None
    assert isinstance(runtime.bus, MemoryBus)
    await runtime.bus.close()
    return done.status, done.attempts


async def test_queued_publication_reaches_the_tracker(
    runtime: Runtime, keitaro: FakeKeitaro
) -> None:
    outcome = await queue_publication(runtime)

    assert outcome == (TaskStatus.SUCCEEDED, 1)
    assert [offer.share for offer in keitaro.streams[OFFERS_STREAM_ID].offers] == [25] * 4
    assert (await runtime.storage.outbox.backlog()).waiting == 0


async def test_tracker_that_stays_down_ends_the_task_after_the_last_attempt(
    runtime: Runtime, keitaro: FakeKeitaro
) -> None:
    keitaro.fail_on.add("replace_stream_offers")

    outcome = await queue_publication(runtime)

    assert outcome == (TaskStatus.REJECTED, MAX_ATTEMPTS)
    assert keitaro.calls["replace_stream_offers"] == MAX_ATTEMPTS
    assert [offer.share for offer in keitaro.streams[OFFERS_STREAM_ID].offers] == [34, 33, 33]
