"""The outbox sender (R-EV-03)."""

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.messaging.memory import MemoryBus
from app.messaging.ports import Message, Queue
from app.messaging.relay import Relay
from app.services.models import OutboxBacklog, OutboxMessage
from app.storage.memory import create_memory_storage
from app.storage.ports import Storage

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
LEASE = timedelta(seconds=30)
TOPIC = "stream.publish.requested"
TASKS = Queue("tasks", (TOPIC,))


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class FlakyBus(MemoryBus):
    """Takes a given number of messages and then loses the connection once."""

    def __init__(self, healthy_for: int) -> None:
        super().__init__([TASKS])
        self._healthy_for = healthy_for
        self.taken: list[Message] = []

    async def publish(self, message: Message) -> None:
        if len(self.taken) == self._healthy_for:
            self._healthy_for = -1
            raise ConnectionError
        self.taken.append(message)


async def queued(storage: Storage, count: int) -> list[OutboxMessage]:
    messages = [
        OutboxMessage(uuid4(), TOPIC, NOW + timedelta(seconds=second), {"n": second})
        for second in range(count)
    ]
    for item in reversed(messages):
        await storage.outbox.put(item)
    return messages


async def test_waiting_messages_leave_in_the_order_they_were_written() -> None:
    """R-EV-03."""
    storage, bus = create_memory_storage(), FlakyBus(healthy_for=-1)
    messages = await queued(storage, 5)
    relay = Relay(storage, bus, clock=Clock(), batch=2)

    sent = [await relay.send_waiting() for _ in range(4)]

    assert sent == [2, 2, 1, 0]
    assert [(item.id, item.topic, item.payload) for item in bus.taken] == [
        (item.id, item.topic, item.payload) for item in messages
    ]
    assert await storage.outbox.backlog() == OutboxBacklog(0, None)


async def test_failure_of_the_bus_loses_nothing() -> None:
    """R-EV-03: the second message is not marked as sent and leaves on a later pass."""
    storage, bus, clock = create_memory_storage(), FlakyBus(healthy_for=1), Clock()
    messages = await queued(storage, 3)
    relay = Relay(storage, bus, clock=clock, lease=LEASE)

    with pytest.raises(ConnectionError):
        await relay.send_waiting()

    assert await storage.outbox.backlog() == OutboxBacklog(2, messages[1].created_at)
    assert await relay.send_waiting() == 0
    clock.now += LEASE
    assert await relay.send_waiting() == 2
    assert [item.id for item in bus.taken] == [item.id for item in messages]


async def test_relay_hands_messages_to_consumers() -> None:
    """R-EV-03, R-EV-05: the whole way from the outbox to a handler."""
    storage, bus = create_memory_storage(), MemoryBus([TASKS])
    got: list[Message] = []

    async def handler(message: Message) -> None:
        got.append(message)

    await bus.consume(TASKS.name, handler)
    messages = await queued(storage, 3)

    await Relay(storage, bus, clock=Clock()).send_waiting()
    await bus.drain()
    await bus.close()

    assert [item.id for item in got] == [item.id for item in messages]


async def test_whoever_wrote_a_message_sends_it_at_once() -> None:
    """R-EV-03: a process without the sender's loop does not wait for another one's poll."""
    storage, bus = create_memory_storage(), FlakyBus(healthy_for=-1)
    messages = await queued(storage, 3)
    relay = Relay(storage, bus, clock=Clock(), batch=2)

    relay.nudge()
    await relay.settle()

    assert [item.id for item in bus.taken] == [item.id for item in messages]
    assert await storage.outbox.backlog() == OutboxBacklog(0, None)


async def test_bus_that_is_away_does_not_reach_whoever_wrote_the_message() -> None:
    """R-EV-03: the request has been answered; the message waits for the relay."""
    storage, bus = create_memory_storage(), FlakyBus(healthy_for=0)
    await queued(storage, 1)
    relay = Relay(storage, bus, clock=Clock())

    relay.nudge()
    await relay.settle()

    assert bus.taken == []
    assert (await storage.outbox.backlog()).waiting == 1


async def test_many_nudges_make_one_sender_at_a_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """R-EV-03: a burst of requests must not open a pass per request."""
    storage, bus = create_memory_storage(), FlakyBus(healthy_for=-1)
    relay = Relay(storage, bus, clock=Clock(), batch=10)
    claim = storage.outbox.claim
    inside = most = 0

    async def watched(*, limit: int, now: datetime, lease: timedelta) -> list[OutboxMessage]:
        nonlocal inside, most
        inside += 1
        most = max(most, inside)
        await asyncio.sleep(0)
        try:
            return await claim(limit=limit, now=now, lease=lease)
        finally:
            inside -= 1

    monkeypatch.setattr(storage.outbox, "claim", watched)

    for number in range(100):
        await storage.outbox.put(OutboxMessage(uuid4(), TOPIC, NOW, {"n": number}))
        relay.nudge()
        await asyncio.sleep(0)
    await relay.settle()

    assert most == 1
    assert len(bus.taken) == 100


async def test_running_relay_is_only_woken() -> None:
    """R-EV-03: where the loop runs, a nudge starts no second sender."""
    storage, bus = create_memory_storage(), FlakyBus(healthy_for=-1)
    relay = Relay(storage, bus, clock=Clock())
    loop = asyncio.create_task(relay.run(poll=60))
    await asyncio.sleep(0.01)
    await queued(storage, 1)

    relay.nudge()
    await asyncio.sleep(0.05)
    sent = len(bus.taken)
    loop.cancel()
    with suppress(asyncio.CancelledError):
        await loop
    await relay.settle()

    assert sent == 1
