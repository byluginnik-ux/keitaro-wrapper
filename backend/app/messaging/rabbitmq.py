import json
import logging
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from uuid import UUID

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractIncomingMessage

from app.messaging.ports import Handler, Message, Queue, QueueStats

log = logging.getLogger(__name__)

ATTEMPT = "x-attempt"


class RabbitBus:
    """RabbitMQ: durable queues, persistent messages, confirmed publishing (R-EV-04).

    A failed message is re-published to `<queue>.retry`, where it waits for the
    delay and is dead-lettered back into the queue; after the last attempt it
    goes to `<queue>.dead` (R-EV-06).
    """

    def __init__(
        self,
        channel: AbstractChannel,
        exchange: AbstractExchange,
        queues: Sequence[Queue],
        *,
        max_attempts: int,
    ) -> None:
        self._channel = channel
        self._exchange = exchange
        self._max_attempts = max_attempts
        self._dead = {queue.name: queue.dead for queue in queues}
        self._names = [name for queue in queues for name in (queue.name, queue.dead)]

    async def publish(self, message: Message) -> None:
        raise NotImplementedError

    async def consume(self, queue: str, handler: Handler) -> None:
        source = await self._channel.get_queue(queue)

        async def on_message(incoming: AbstractIncomingMessage) -> None:
            message = _incoming(incoming)
            try:
                await handler(message)
            except Exception:  # any failure of a handler means «deliver again»
                log.warning("handler of %s failed on %s", queue, message.id, exc_info=True)
                await self._fail(queue, message)
            await incoming.ack()

        await source.consume(on_message)

    async def stats(self) -> list[QueueStats]:
        """Ask the broker itself: aio-pika remembers the numbers of the first declaration."""
        broker = await self._channel.get_underlay_channel()
        found: list[QueueStats] = []
        for name in self._names:
            result = await broker.queue_declare(queue=name, passive=True)
            found.append(QueueStats(name, result.message_count or 0, result.consumer_count or 0))
        return found

    async def _fail(self, queue: str, message: Message) -> None:
        dead = self._dead.get(queue)
        if dead is None:
            return  # a failed dead letter stays handled: there is nowhere further to put it
        last = message.attempt >= self._max_attempts
        target = dead if last else f"{queue}.retry"
        again = (
            message
            if last
            else Message(message.id, message.topic, message.payload, message.attempt + 1)
        )
        await self._channel.default_exchange.publish(_outgoing(again), routing_key=target)


def _outgoing(message: Message) -> aio_pika.Message:
    return aio_pika.Message(
        body=json.dumps(message.payload).encode(),
        message_id=str(message.id),
        type=message.topic,
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        headers={ATTEMPT: message.attempt},
    )


def _incoming(incoming: AbstractIncomingMessage) -> Message:
    attempt = incoming.headers.get(ATTEMPT, 1)
    return Message(
        id=UUID(incoming.message_id),
        topic=incoming.type or incoming.routing_key or "",
        payload=json.loads(incoming.body),
        attempt=attempt if isinstance(attempt, int) else 1,
    )


@asynccontextmanager
async def open_rabbit_bus(  # noqa: PLR0913 — every knob is a setting of the deployment
    url: str,
    queues: Sequence[Queue],
    *,
    exchange: str = "keitaro",
    max_attempts: int = 3,
    retry_delay: float = 5.0,
    prefetch: int = 10,
) -> AsyncGenerator[RabbitBus]:
    """Connect, declare the exchange and every queue with its retry and dead-letter queues."""
    connection = await aio_pika.connect_robust(url)
    async with connection:
        channel = await connection.channel(publisher_confirms=True)
        await channel.set_qos(prefetch_count=prefetch)
        topics = await channel.declare_exchange(exchange, aio_pika.ExchangeType.TOPIC, durable=True)
        for queue in queues:
            main = await channel.declare_queue(queue.name, durable=True)
            for topic in queue.topics:
                await main.bind(topics, routing_key=topic)
            await channel.declare_queue(queue.dead, durable=True)
            await channel.declare_queue(
                f"{queue.name}.retry",
                durable=True,
                arguments={
                    "x-message-ttl": int(retry_delay * 1000),
                    "x-dead-letter-exchange": "",
                    "x-dead-letter-routing-key": queue.name,
                },
            )
        yield RabbitBus(channel, topics, queues, max_attempts=max_attempts)
