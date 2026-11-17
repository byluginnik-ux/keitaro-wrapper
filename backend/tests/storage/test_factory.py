import pytest
from pydantic import SecretStr
from sqlalchemy.pool import QueuePool

from app.settings import Settings
from app.storage.factory import create_engine, create_mongo_client, open_storage
from tests.storage.test_contract import campaign

pytestmark = pytest.mark.anyio


async def test_memory_backend_needs_no_database() -> None:
    """R-ST-03."""
    settings = Settings(keitaro_api_key=SecretStr("fake-key"), storage_backend="memory")

    async with open_storage(settings) as storage:
        saved = campaign()
        await storage.campaigns.add(saved)

        assert await storage.campaigns.get(saved.id) == saved


async def test_postgres_backend_uses_the_configured_database(postgres_url: str) -> None:
    """R-ST-02, R-ST-03."""
    settings = Settings(
        keitaro_api_key=SecretStr("fake-key"), storage_backend="postgres", database_url=postgres_url
    )

    async with open_storage(settings) as storage:
        assert await storage.campaigns.get_by_keitaro_id(-1) is None


async def test_mongo_backend_uses_the_configured_database(mongo_url: str) -> None:
    """R-ST-03: the same services run on MongoDB by changing one variable."""
    settings = Settings(
        keitaro_api_key=SecretStr("fake-key"),
        storage_backend="mongo",
        mongo_url=mongo_url,
        mongo_database="keitaro_test",
    )

    async with open_storage(settings) as storage:
        assert await storage.campaigns.get_by_keitaro_id(-1) is None


def test_unknown_backend_is_rejected() -> None:
    """R-ST-03."""
    with pytest.raises(ValueError, match="storage_backend"):
        Settings(keitaro_api_key=SecretStr("fake-key"), storage_backend="sqlite")  # pyright: ignore[reportArgumentType] — the point of the test


async def test_sizes_of_the_pools_come_from_the_settings() -> None:
    """R-OPS-05: nothing connects until the first query, so no database is needed."""
    settings = Settings(
        keitaro_api_key=SecretStr("fake-key"),
        database_url="postgresql+asyncpg://nobody@127.0.0.1:1/none",
        mongo_url="mongodb://127.0.0.1:1/?directConnection=true",
        db_pool_size=7,
        db_max_overflow=3,
        mongo_max_pool_size=11,
    )

    engine, client = create_engine(settings), create_mongo_client(settings)
    try:
        pool = engine.sync_engine.pool
        assert isinstance(pool, QueuePool)
        assert (pool.size(), pool._max_overflow) == (7, 3)  # noqa: SLF001 — the pool has no public reader for it  # pyright: ignore[reportPrivateUsage]
        assert client.options.pool_options.max_pool_size == 11
    finally:
        await engine.dispose()
        await client.close()
