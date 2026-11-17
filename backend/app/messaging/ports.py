from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.services.models import Payload


@dataclass(frozen=True, slots=True)
class Message:
    """What travels through the bus; `attempt` counts deliveries to one queue."""

    id: UUID
    topic: str
    payload: Payload
    attempt: int = 1


type Handler = Callable[[Message], Awaitable[None]]
"""Returning means «done»; raising means «deliver again later» (R-EV-06)."""


@dataclass(frozen=True, slots=True)
class Queue:
    """A named queue and the topics it receives (R-EV-05)."""

    name: str
    topics: tuple[str, ...]

    @property
    def dead(self) -> str:
        """Where messages go after the last failed attempt."""
        return f"{self.name}.dead"


@dataclass(frozen=True, slots=True)
class QueueStats:
    name: str
    ready: int
    consumers: int


class MessageBus(Protocol):
    """Topics in, queues out. Delivery is at least once: handlers must bear a repeat."""

    async def publish(self, message: Message) -> None:
        """Hand the message over; returning means the bus has taken it (R-EV-03)."""
        ...

    async def consume(self, queue: str, handler: Handler) -> None:
        """Start feeding the queue (or its dead-letter queue) to the handler."""
        ...

    async def stats(self) -> list[QueueStats]:
        """Tell how many messages wait in every queue and who listens."""
        ...
