"""The outbox sender as its own process: `python -m app.relay` (R-EV-03)."""

import asyncio

from app.runtime import open_runtime
from app.settings import Settings


async def main() -> None:
    """Send the outbox until the process is stopped."""
    settings = Settings()  # pyright: ignore[reportCallIssue] — values come from the environment
    async with open_runtime(settings) as runtime:
        await runtime.relay.run(poll=settings.outbox_poll)


if __name__ == "__main__":
    asyncio.run(main())
