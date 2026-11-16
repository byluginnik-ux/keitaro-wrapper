import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.storage.memory import create_memory_storage
from app.storage.ports import Storage
from app.storage.sqlalchemy.adapter import create_sqlalchemy_storage

BACKEND = Path(__file__).parent.parent.parent
TABLES = "audit_log, stream_offers, streams, campaigns"


def unavailable(name: str, variable: str) -> None:
    """Skip locally, fail where every adapter must be proven (R-ST-04)."""
    message = f"{name}: set {variable} (see `docker compose --profile test up -d`)"
    if os.environ.get("REQUIRE_STORAGE_TESTS"):
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture(scope="session")
def postgres_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        unavailable("postgres", "TEST_DATABASE_URL")
        raise AssertionError  # unreachable: both branches above raise
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": url},
        check=True,
    )
    return url


@pytest.fixture
async def sqlalchemy_storage(postgres_url: str) -> AsyncIterator[Storage]:
    engine = create_async_engine(postgres_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield create_sqlalchemy_storage(engine)
    await engine.dispose()


@pytest.fixture(params=["memory", "sqlalchemy"])
def storage(request: pytest.FixtureRequest) -> Storage:
    """Every adapter runs the same contract (R-ST-04)."""
    if request.param == "memory":
        return create_memory_storage()
    return request.getfixturevalue(f"{request.param}_storage")
