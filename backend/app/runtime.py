"""What the web process, the outbox sender and the worker are assembled from."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass

from app.keitaro.client import KeitaroClient, create_http_client
from app.keitaro.gateway import KeitaroGateway
from app.messaging.memory import MemoryBus
from app.messaging.ports import Message, MessageBus, Queue
from app.messaging.rabbitmq import open_rabbit_bus
from app.messaging.relay import Relay
from app.services.catalog import CatalogService
from app.services.creator import CREATE_REQUESTED, CreatorService
from app.services.editor import EditorService
from app.services.publisher import PUBLISH_REQUESTED, PublisherService
from app.services.tasks import TasksService
from app.settings import Settings
from app.storage.factory import open_storage
from app.storage.ports import Storage

TASKS = Queue("keitaro.tasks", (PUBLISH_REQUESTED, CREATE_REQUESTED))
QUEUES = (TASKS,)


@dataclass(frozen=True, slots=True)
class Runtime:
    storage: Storage
    bus: MessageBus
    relay: Relay
    catalog: CatalogService
    creator: CreatorService
    editor: EditorService
    publisher: PublisherService
    tasks: TasksService

    async def consume_tasks(self) -> None:
        """Start doing the queued work in this process."""
        await self.bus.consume(TASKS.name, self._handle)
        await self.bus.consume(TASKS.dead, self._bury)

    async def _handle(self, message: Message) -> None:
        """Give the message to the service its topic belongs to."""
        service = self.creator if message.topic == CREATE_REQUESTED else self.publisher
        await service.handle(message)

    async def _bury(self, message: Message) -> None:
        service = self.creator if message.topic == CREATE_REQUESTED else self.publisher
        await service.bury(message)


@asynccontextmanager
async def open_bus(settings: Settings) -> AsyncGenerator[MessageBus]:
    """Open the bus chosen by MESSAGE_BUS (R-EV-04)."""
    if settings.message_bus == "rabbitmq":
        async with open_rabbit_bus(
            settings.rabbitmq_url,
            QUEUES,
            max_attempts=settings.task_max_attempts,
            retry_delay=settings.task_retry_delay,
        ) as rabbit:
            yield rabbit
        return
    memory = MemoryBus(
        QUEUES, max_attempts=settings.task_max_attempts, retry_delay=settings.task_retry_delay
    )
    try:
        yield memory
    finally:
        await memory.close()


def assemble(
    settings: Settings, keitaro: KeitaroGateway, storage: Storage, bus: MessageBus
) -> Runtime:
    """Wire the services to their tracker, storage and bus."""
    catalog = CatalogService(keitaro)
    relay = Relay(storage, bus)
    creator = CreatorService(
        keitaro,
        catalog,
        storage,
        name_prefix=settings.campaign_name_prefix,
        max_attempts=settings.task_max_attempts,
        announce=relay.nudge,
    )
    publisher = PublisherService(
        keitaro, storage, max_attempts=settings.task_max_attempts, announce=relay.nudge
    )
    return Runtime(
        storage=storage,
        bus=bus,
        relay=relay,
        catalog=catalog,
        creator=creator,
        editor=EditorService(keitaro, catalog, storage),
        publisher=publisher,
        tasks=TasksService(storage, bus, publisher, creator),
    )


@asynccontextmanager
async def open_runtime(settings: Settings) -> AsyncGenerator[Runtime]:
    """Open everything a process needs and close it in the reverse order.

    With the in-memory bus there are no other processes to send the outbox and to
    do the work, so this one does both.
    """
    async with (
        create_http_client(
            settings.keitaro_base_url, settings.keitaro_api_key.get_secret_value()
        ) as http,
        open_storage(settings) as storage,
        open_bus(settings) as bus,
    ):
        runtime = assemble(settings, KeitaroClient(http), storage, bus)
        if settings.message_bus != "memory":
            yield runtime
            return
        await runtime.consume_tasks()
        sending = asyncio.create_task(runtime.relay.run(poll=settings.outbox_poll))
        try:
            yield runtime
        finally:
            sending.cancel()
            with suppress(asyncio.CancelledError):
                await sending
