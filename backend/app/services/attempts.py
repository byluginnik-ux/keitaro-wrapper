"""What every queued task goes through, whatever it does (R-TK-04, R-EV-07, 08)."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from app.messaging.ports import Message
from app.services.errors import KeitaroError, TaskKeyReusedError
from app.services.models import Task, TaskStatus, TaskStep
from app.storage.errors import StorageConflictError
from app.storage.ports import Storage

SERVER_ERROR = 500


def utc_now() -> datetime:
    """Return the current moment; replaced in tests."""
    return datetime.now(UTC)


def same_task(known: Task, fingerprint: str) -> Task:
    """Answer a repeated task ID with its task, unless it now names another request (R-TK-04)."""
    if known.fingerprint != fingerprint:
        raise TaskKeyReusedError
    return known


def is_transient(error: KeitaroError) -> bool:
    """Tell a failure worth another attempt (no answer, 5xx) from a refusal (R-EV-08)."""
    return error.status is None or error.status >= SERVER_ERROR


async def unfinished(storage: Storage, message: Message) -> Task | None:
    """Read the task of a message; a task that is gone or has ended needs nothing more."""
    task = await storage.tasks.get(UUID(message.payload["task_id"]))
    return None if task is None or task.status.final else task


async def ended(storage: Storage, task_id: UUID) -> bool:
    """Tell whether somebody else has written the outcome of the task.

    A refused write of an outcome means another delivery got there first only if the
    task has ended. Otherwise stepping aside would leave it running for ever.
    """
    task = await storage.tasks.get(task_id)
    return task is None or task.status.final


async def begin(storage: Storage, message: Message, clock: Callable[[], datetime]) -> Task | None:
    """Mark the task as running and count the attempt; None means this delivery steps aside.

    The write names the status the task was read in, so a task cancelled or taken
    by another delivery in between is left alone (R-EV-07).
    """
    task = await unfinished(storage, message)
    if task is None:
        return None
    now = clock()
    running = replace(
        task,
        status=TaskStatus.RUNNING,
        attempts=task.attempts + 1,
        started_at=task.started_at or now,
        steps=(*task.steps, TaskStep("attempt", now, str(task.attempts + 1))),
    )
    try:
        await storage.tasks.save(running, was=task.status)
    except StorageConflictError:
        return None
    return running
