import pytest

from app.settings import Settings
from app.storage.factory import open_storage
from tests.storage.test_contract import campaign

pytestmark = pytest.mark.anyio


async def test_memory_backend_needs_no_database() -> None:
    """R-ST-03."""
    settings = Settings(keitaro_api_key="fake-key", storage_backend="memory")

    async with open_storage(settings) as storage:
        saved = campaign()
        await storage.campaigns.add(saved)

        assert await storage.campaigns.get(saved.id) == saved


async def test_postgres_backend_uses_the_configured_database(postgres_url: str) -> None:
    """R-ST-02, R-ST-03."""
    settings = Settings(keitaro_api_key="fake-key", database_url=postgres_url)

    async with open_storage(settings) as storage:
        assert await storage.campaigns.get_by_keitaro_id(-1) is None


def test_unknown_backend_is_rejected() -> None:
    """R-ST-03."""
    with pytest.raises(ValueError, match="storage_backend"):
        Settings(keitaro_api_key="fake-key", storage_backend="sqlite")  # pyright: ignore[reportArgumentType] — the point of the test
