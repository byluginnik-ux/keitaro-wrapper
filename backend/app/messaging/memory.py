import asyncio
import logging
from collections.abc import Sequence
from dataclasses import replace

from app.messaging.ports import Handler, Message, Queue, QueueStats

log = logging.getLogger(__name__)


class MemoryBus:
    """The bus inside one process: for tests and for running without a broker (R-EV-04)."""

    def __init__(
        self, queues: Sequence[Queue], *, max_attempts: int = 3, retry_delay: float = 0.0
    ) -> None:
        self._max_attempts = max_attempts
        self._retry_delay = retry_delay
        self._dead = {queue.name: queue.dead for queue in queues}
        self._queues: dict[str, asyncio.Queue[Message]] = {
            name: asyncio.Queue() for queue in queues for name in (queue.name, queue.dead)
        }
        self._routes: dict[str, list[str]] = {}
        for queue in queues:
            for topic in queue.topics:
                self._routes.setdefault(topic, []).append(queue.name)
        self._consumers: dict[str, list[asyncio.Task[None]]] = {name: [] for name in self._queues}
        self._retries: set[asyncio.Task[None]] = set()

    async def publish(self, message: Message) -> None:
        raise NotImplementedError

    async def consume(self, queue: str, handler: Handler) -> None:
        self._consumers[queue].append(asyncio.create_task(self._serve(queue, handler)))

    async def stats(self) -> list[QueueStats]:
        return [
            QueueStats(name, queue.qsize(), len(self._consumers[name]))
            for name, queue in self._queues.items()
        ]

    async def drain(self) -> None:
        """Wait until every message, retries included, has been handled; for tests."""
        while True:
            listened = [self._queues[name] for name, tasks in self._consumers.items() if tasks]
            await asyncio.gather(*(queue.join() for queue in listened))
            if not self._retries:
                return
            await asyncio.gather(*self._retries)

    async def close(self) -> None:
        tasks = [task for tasks in self._consumers.values() for task in tasks] + [*self._retries]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _serve(self, name: str, handler: Handler) -> None:
        queue = self._queues[name]
        while True:
            message = await queue.get()
            try:
                await handler(message)
            except Exception:  # any failure of a handler means «deliver again»
                log.warning("handler of %s failed on %s", name, message.id, exc_info=True)
                self._fail(name, message)
            finally:
                queue.task_done()

    def _fail(self, name: str, message: Message) -> None:
        dead = self._dead.get(name)
        if dead is None:
            return  # a failed dead letter stays handled: there is nowhere further to put it
        if message.attempt >= self._max_attempts:
            self._queues[dead].put_nowait(message)
            return
        retry = asyncio.create_task(self._redeliver(name, message))
        self._retries.add(retry)
        retry.add_done_callback(self._retries.discard)

    async def _redeliver(self, name: str, message: Message) -> None:
        await asyncio.sleep(self._retry_delay)
        self._queues[name].put_nowait(replace(message, attempt=message.attempt + 1))
