"""One contract for the in-memory bus and RabbitMQ (R-EV-04…06)."""

import asyncio
from uuid import uuid4

import pytest

from app.messaging.ports import Message, MessageBus, Queue, QueueStats
from tests.messaging.conftest import MAX_ATTEMPTS, eventually

pytestmark = pytest.mark.anyio


def message(topic: str, **payload: object) -> Message:
    return Message(uuid4(), topic, dict(payload))


class Recorder:
    """A handler that remembers what it got and fails as many times as told."""

    def __init__(self, failures: int = 0) -> None:
        self.got: list[Message] = []
        self._failures = failures

    async def __call__(self, message: Message) -> None:
        self.got.append(message)
        if len(self.got) <= self._failures:
            raise RuntimeError


async def test_message_reaches_the_queue_of_its_topic_as_sent(
    bus: MessageBus, queues: list[Queue]
) -> None:
    """R-EV-05."""
    tasks, events = Recorder(), Recorder()
    await bus.consume(queues[0].name, tasks)
    await bus.consume(queues[1].name, events)
    sent = message(
        queues[0].topics[1], task_id=str(uuid4()), offers=[{"offer_id": 1, "share": 100}]
    )

    await bus.publish(sent)
    await bus.publish(message("nobody.listens"))
    await eventually(lambda: bool(tasks.got))

    assert tasks.got == [sent]
    assert events.got == []


async def test_message_waits_for_a_handler_that_starts_later(
    bus: MessageBus, queues: list[Queue]
) -> None:
    """R-EV-05."""
    first, second = message(queues[0].topics[0], n=1), message(queues[0].topics[0], n=2)
    await bus.publish(first)
    await bus.publish(second)
    await eventually_ready(bus, queues[0].name, 2)

    late = Recorder()
    await bus.consume(queues[0].name, late)
    await eventually(lambda: len(late.got) == 2)

    assert late.got == [first, second]
    assert QueueStats(queues[0].name, 0, 1) in await bus.stats()


async def test_failed_message_comes_again_with_the_attempt_number(
    bus: MessageBus, queues: list[Queue]
) -> None:
    """R-EV-06."""
    flaky = Recorder(failures=1)
    await bus.consume(queues[0].name, flaky)
    sent = message(queues[0].topics[0], n=1)

    await bus.publish(sent)
    await eventually(lambda: len(flaky.got) == 2)
    await asyncio.sleep(0.2)

    assert [(item.id, item.payload, item.attempt) for item in flaky.got] == [
        (sent.id, sent.payload, 1),
        (sent.id, sent.payload, 2),
    ]


async def test_message_that_keeps_failing_ends_in_the_dead_queue(
    bus: MessageBus, queues: list[Queue]
) -> None:
    """R-EV-06."""
    broken, buried = Recorder(failures=100), Recorder()
    await bus.consume(queues[0].name, broken)
    await bus.consume(queues[0].dead, buried)
    sent = message(queues[0].topics[0], n=1)

    await bus.publish(sent)
    await eventually(lambda: bool(buried.got))
    await asyncio.sleep(0.2)

    assert [item.attempt for item in broken.got] == list(range(1, MAX_ATTEMPTS + 1))
    assert [(item.id, item.topic, item.payload) for item in buried.got] == [
        (sent.id, sent.topic, sent.payload)
    ]


async def eventually_ready(bus: MessageBus, queue: str, count: int) -> None:
    """The broker counts a message as ready a moment after it confirmed it."""
    async with asyncio.timeout(5):
        while QueueStats(queue, count, 0) not in await bus.stats():  # noqa: ASYNC110 — polling is what a test of a broker does
            await asyncio.sleep(0.02)
