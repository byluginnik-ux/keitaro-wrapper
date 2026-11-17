from collections.abc import Collection, Sequence
from datetime import datetime, timedelta
from uuid import UUID

from app.services.models import OutboxBacklog, OutboxMessage, Task, TaskKind, TaskStatus


class PendingTasks:
    """Tasks are not stored yet."""

    async def add(self, task: Task) -> None:
        raise NotImplementedError

    async def get(self, task_id: UUID) -> Task | None:
        raise NotImplementedError

    async def save(self, task: Task, *, was: TaskStatus) -> None:
        raise NotImplementedError

    async def list_recent(
        self,
        *,
        statuses: Collection[TaskStatus] = (),
        kind: TaskKind | None = None,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[Task]:
        raise NotImplementedError

    async def count_by_status(self) -> dict[TaskStatus, int]:
        raise NotImplementedError


class PendingOutbox:
    """The outbox is not stored yet."""

    async def put(self, message: OutboxMessage) -> None:
        raise NotImplementedError

    async def claim(self, *, limit: int, now: datetime, lease: timedelta) -> list[OutboxMessage]:
        raise NotImplementedError

    async def mark_sent(self, ids: Sequence[UUID], now: datetime) -> None:
        raise NotImplementedError

    async def backlog(self) -> OutboxBacklog:
        raise NotImplementedError
