"""The handler of queued tasks as its own process: `python -m app.worker` (R-EV-07, 08)."""

import asyncio
import signal

from app.runtime import open_runtime
from app.settings import Settings


async def main() -> None:
    """Handle queued tasks until the process is told to stop."""
    settings = Settings()  # pyright: ignore[reportCallIssue] — values come from the environment
    stop = asyncio.Event()
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stop.set)
    async with open_runtime(settings) as runtime:
        if settings.message_bus != "memory":
            await runtime.consume_tasks()
        await stop.wait()


if __name__ == "__main__":
    asyncio.run(main())
