import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from pymongo import AsyncMongoClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.storage.memory import create_memory_storage
from app.storage.mongo.adapter import create_mongo_storage, prepare
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


@pytest.fixture(scope="session")
def mongo_url() -> str:
    url = os.environ.get("TEST_MONGO_URL")
    if not url:
        unavailable("mongo", "TEST_MONGO_URL")
        raise AssertionError  # unreachable: both branches above raise
    return url


@pytest.fixture
async def mongo_storage(mongo_url: str) -> AsyncIterator[Storage]:
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        mongo_url, uuidRepresentation="standard", tz_aware=True
    )
    await client.drop_database("keitaro_test")
    database = client["keitaro_test"]
    await prepare(database)
    yield create_mongo_storage(database)
    await client.close()


@pytest.fixture(params=["memory", "sqlalchemy", "mongo"])
def storage(request: pytest.FixtureRequest) -> Storage:
    """Every adapter runs the same contract (R-ST-04)."""
    if request.param == "memory":
        return create_memory_storage()
    return request.getfixturevalue(f"{request.param}_storage")
