from datetime import UTC, datetime

from app.graphql.context import Context
from app.services.catalog import CatalogService
from app.services.creator import CreatorService
from app.storage.memory import create_memory_storage
from app.storage.ports import Storage
from tests.fakes import FakeKeitaro

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
PREFIX = "test_bulygin_"


def context_for(keitaro: FakeKeitaro, storage: Storage | None = None) -> Context:
    """Wire real services to the fake tracker and in-memory storage."""
    catalog = CatalogService(keitaro)
    creator = CreatorService(
        keitaro,
        catalog,
        storage or create_memory_storage(),
        name_prefix=PREFIX,
        clock=lambda: NOW,
        new_alias=lambda: "alias001",
    )
    return Context(catalog=catalog, creator=creator)
