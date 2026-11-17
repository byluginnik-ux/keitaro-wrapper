from collections.abc import Callable, Collection
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from app.messaging.ports import MessageBus, QueueStats
from app.services.creator import utc_now
from app.services.errors import (
    TaskNotCancellableError,
    TaskNotFoundError,
    TaskNotRetryableError,
)
from app.services.models import OutboxBacklog, Task, TaskKind, TaskStatus, TaskStep
from app.services.publisher import PublisherService
from app.storage.errors import StorageConflictError
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
        limit = max(1, min(limit, MAX_LISTED))
        return await self._storage.tasks.list_recent(statuses=statuses, kind=kind, limit=limit)

    async def summary(self) -> QueueSummary:
        return QueueSummary(
            tasks=await self._storage.tasks.count_by_status(),
            outbox=await self._storage.outbox.backlog(),
            queues=await self._bus.stats(),
        )

    async def cancel(self, task_id: UUID) -> Task:
        """Take a waiting task back and free its stream; the draft stays (R-TK-08)."""
        task = await self._storage.tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError
        if task.status is not TaskStatus.PENDING:
            raise TaskNotCancellableError
        now = self._clock()
        cancelled = replace(
            task,
            status=TaskStatus.CANCELLED,
            finished_at=now,
            steps=(*task.steps, TaskStep("cancelled", now)),
        )
        try:
            async with self._storage.transaction() as work:
                await work.tasks.save(cancelled, was=TaskStatus.PENDING)
                stream = await work.streams.get(task.stream_id) if task.stream_id else None
                if stream is not None and stream.publishing == task.id:
                    await work.streams.save(replace(stream, publishing=None))
        except StorageConflictError as error:
            raise TaskNotCancellableError from error  # a worker took the task first
        return cancelled

    async def retry(self, task_id: UUID, new_task_id: UUID) -> Task:
        """Queue the rejected publication again as a new task (R-TK-09)."""
        task = await self._storage.tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError
        retryable = task.kind is TaskKind.PUBLISH_STREAM and task.status is TaskStatus.REJECTED
        if not retryable or task.stream_id is None:
            raise TaskNotRetryableError
        return await self._publisher.request(task.stream_id, new_task_id, retry_of=task.id)
