from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.messaging.ports import MessageBus, QueueStats
from app.services.creator import utc_now
from app.services.models import OutboxBacklog, Task, TaskKind, TaskStatus
from app.services.publisher import PublisherService
from app.storage.ports import Storage

MAX_LISTED = 200


@dataclass(frozen=True, slots=True)
class QueueSummary:
    """Where the queued work is right now (R-TK-07)."""

    tasks: dict[TaskStatus, int]
    outbox: OutboxBacklog
    queues: list[QueueStats]


class TasksService:
    """Look at the tasks and steer them: list, cancel, repeat (R-TK-06…09)."""

    def __init__(
        self,
        storage: Storage,
        bus: MessageBus,
        publisher: PublisherService,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._storage = storage
        self._bus = bus
        self._publisher = publisher
        self._clock = clock

    async def recent(
        self,
        *,
        statuses: Collection[TaskStatus] = (),
        kind: TaskKind | None = None,
        limit: int = 50,
    ) -> list[Task]:
        raise NotImplementedError

    async def summary(self) -> QueueSummary:
        raise NotImplementedError

    async def cancel(self, task_id: UUID) -> Task:
        """Take a waiting task back and free its stream; the draft stays (R-TK-08)."""
        raise NotImplementedError

    async def retry(self, task_id: UUID, new_task_id: UUID) -> Task:
        """Queue the rejected publication again as a new task (R-TK-09)."""
        raise NotImplementedError
