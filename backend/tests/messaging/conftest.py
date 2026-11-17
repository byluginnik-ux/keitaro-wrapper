import asyncio
import os
from collections.abc import AsyncIterator, Callable
from uuid import uuid4

import pytest

from app.messaging.memory import MemoryBus
from app.messaging.ports import MessageBus, Queue
from app.messaging.rabbitmq import open_rabbit_bus

MAX_ATTEMPTS = 3


@pytest.fixture
def queues() -> list[Queue]:
    """Fresh names for every test: the broker keeps queues between tests."""
    run = uuid4().hex[:8]
    return [
        Queue(f"test.{run}.tasks", (f"{run}.publish.requested", f"{run}.create.requested")),
        Queue(f"test.{run}.events", (f"{run}.published",)),
    ]


@pytest.fixture(params=["memory", "rabbitmq"])
async def bus(request: pytest.FixtureRequest, queues: list[Queue]) -> AsyncIterator[MessageBus]:
    """Every bus runs the same contract (R-EV-04)."""
    if request.param == "memory":
        memory = MemoryBus(queues, max_attempts=MAX_ATTEMPTS, retry_delay=0.01)
        yield memory
        await memory.close()
        return
    url = os.environ.get("TEST_RABBITMQ_URL")
    if not url:
        message = "rabbitmq: set TEST_RABBITMQ_URL (see `docker compose --profile test up -d`)"
        if os.environ.get("REQUIRE_BROKER_TESTS"):
            pytest.fail(message)
        pytest.skip(message)
    async with open_rabbit_bus(
        url, queues, exchange=queues[0].name, max_attempts=MAX_ATTEMPTS, retry_delay=0.05
    ) as rabbit:
        yield rabbit


async def eventually(condition: Callable[[], bool], timeout: float = 5.0) -> None:  # noqa: ASYNC109 — a plain deadline of a test helper
    """Wait for something a consumer does in the background."""
    async with asyncio.timeout(timeout):
        while not condition():  # noqa: ASYNC110 — polling is what a test of a broker does
            await asyncio.sleep(0.01)
