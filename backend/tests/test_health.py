from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.cache.ports import CacheUnavailableError
from app.main import create_app
from app.messaging.ports import QueueStats
from app.settings import Settings

pytestmark = pytest.mark.anyio


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def http(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_health_reports_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_when_storage_bus_and_cache_answer(http: AsyncClient) -> None:
    """R-OPS-04."""
    response = await http.get("/health/ready")

    assert (response.status_code, response.json()) == (200, {"status": "ready", "failed": []})


class BrokenCache:
    async def get_or_load(self, key: str, ttl: float, load: Callable[[], Awaitable[str]]) -> str:
        del ttl, load
        raise CacheUnavailableError(key)

    async def drop(self, key: str) -> None:
        raise CacheUnavailableError(key)

    async def ping(self) -> None:
        raise CacheUnavailableError


async def test_not_ready_without_the_cache(app: FastAPI, http: AsyncClient) -> None:
    """R-OPS-04: the process is alive, but must not be given requests."""
    app.state.runtime = replace(app.state.runtime, cache=BrokenCache())

    ready = await http.get("/health/ready")
    alive = await http.get("/health")

    assert (ready.status_code, ready.json()) == (
        503,
        {"status": "unavailable", "failed": ["cache"]},
    )
    assert alive.status_code == 200


async def test_not_ready_without_the_bus_or_the_storage(
    app: FastAPI, http: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-OPS-04: every part that does not answer is named."""

    async def down() -> list[QueueStats]:
        raise ConnectionError

    async def lost() -> dict[object, int]:
        raise ConnectionError

    monkeypatch.setattr(app.state.runtime.bus, "stats", down)
    monkeypatch.setattr(app.state.runtime.storage.tasks, "count_by_status", lost)

    response = await http.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["failed"] == ["storage", "bus"]


async def test_part_that_hangs_counts_as_unavailable(
    app: FastAPI, http: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-OPS-04: a check has its time."""
    import asyncio  # noqa: PLC0415

    async def hang() -> list[QueueStats]:
        await asyncio.sleep(60)
        return []

    monkeypatch.setattr(app.state.runtime.bus, "stats", hang)
    monkeypatch.setattr("app.main.READY_TIMEOUT", 0.05)

    response = await http.get("/health/ready")

    assert response.json()["failed"] == ["bus"]
