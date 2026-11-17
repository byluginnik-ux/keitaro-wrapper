import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID

from app.messaging.ports import Message, MessageBus
from app.services.attempts import utc_now
from app.storage.ports import Storage

log = logging.getLogger(__name__)


class Relay:
    """Move messages from the outbox to the bus, oldest first (R-EV-03).

    A message is marked as sent only after the bus took it. Whatever was claimed
    and not sent comes back when its lease runs out, so nothing is lost and a
    message may arrive twice.
    """

    def __init__(
        self,
        storage: Storage,
        bus: MessageBus,
        *,
        clock: Callable[[], datetime] = utc_now,
        batch: int = 50,
        lease: timedelta = timedelta(seconds=30),
    ) -> None:
        self._storage = storage
        self._bus = bus
        self._clock = clock
        self._batch = batch
        self._lease = lease
        self._wake = asyncio.Event()

    async def send_waiting(self) -> int:
        """Make one pass and tell how many messages left."""
        claimed = await self._storage.outbox.claim(
            limit=self._batch, now=self._clock(), lease=self._lease
        )
        sent = list[UUID]()
        try:
            for message in claimed:
                await self._bus.publish(Message(message.id, message.topic, message.payload))
                sent.append(message.id)
        finally:
            await self._storage.outbox.mark_sent(sent, self._clock())
        return len(sent)

    async def settle(self) -> None:
        """Wait for whatever this process is sending on its own."""
        raise NotImplementedError

    def nudge(self) -> None:
        """Tell the relay that something was just written; it need not wait for the next poll."""
        self._wake.set()

    async def run(self, *, poll: float = 0.5) -> None:
        """Keep sending until cancelled; a failed pass is repeated after the pause."""
        while True:
            self._wake.clear()
            try:
                full = await self.send_waiting() >= self._batch
            except Exception:  # the bus or the database is away; try again
                log.warning("outbox pass failed", exc_info=True)
                full = False
            if not full:
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=poll)
                except TimeoutError:
                    continue
