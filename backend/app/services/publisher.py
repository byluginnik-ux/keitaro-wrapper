from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.keitaro.gateway import KeitaroGateway
from app.messaging.ports import Message
from app.services.creator import utc_now
from app.services.models import Task
from app.storage.ports import Storage

PUBLISH_REQUESTED = "stream.publish.requested"
PUBLISHED = "stream.published"
PUBLISH_REJECTED = "stream.publish.rejected"


def _nothing() -> None:
    return None


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

    async def request(self, stream_id: UUID, task_id: UUID, *, expected: int | None = None) -> Task:
        raise NotImplementedError

    async def handle(self, message: Message) -> None:
        raise NotImplementedError

    async def bury(self, message: Message) -> None:
        raise NotImplementedError
