"""The outbox sender as its own process: `python -m app.relay` (R-EV-03)."""

import asyncio
import signal
from contextlib import suppress

from app.runtime import open_runtime
from app.settings import Settings


async def main() -> None:
    """Send the outbox until the process is told to stop (R-OPS-03)."""
    settings = Settings()  # pyright: ignore[reportCallIssue] — values come from the environment
    stop = asyncio.Event()
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stop.set)
    async with open_runtime(settings) as runtime:
        sending = asyncio.create_task(runtime.relay.run(poll=settings.outbox_poll))
        stopped = asyncio.create_task(stop.wait())
        await asyncio.wait({sending, stopped}, return_when=asyncio.FIRST_COMPLETED)
        stopped.cancel()
        sending.cancel()
        with suppress(asyncio.CancelledError):
            await sending  # a failure of the sender is raised here and ends the process


if __name__ == "__main__":
    asyncio.run(main())
