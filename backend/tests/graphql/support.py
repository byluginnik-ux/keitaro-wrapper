from datetime import UTC, datetime

from app.graphql.context import Context, ServiceInfo
from app.services.catalog import CatalogService
from app.services.creator import CreatorService
from app.services.editor import EditorService
from app.storage.memory import create_memory_storage
from app.storage.ports import Storage
from tests.fakes import FakeKeitaro

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
PREFIX = "test_bulygin_"


def context_for(
    keitaro: FakeKeitaro, storage: Storage | None = None, *, offers_ttl: float = 30.0
) -> Context:
    """Wire real services to the fake tracker and in-memory storage."""
    catalog = CatalogService(keitaro, offers_ttl=offers_ttl)
    storage = storage or create_memory_storage()
    creator = CreatorService(
        keitaro,
        catalog,
        storage,
        name_prefix=PREFIX,
        clock=lambda: NOW,
        new_alias=lambda: "alias001",
    )
    editor = EditorService(keitaro, catalog, storage, clock=lambda: NOW)
    service = ServiceInfo(campaign_name_prefix=PREFIX, tracker_url="https://tracker.test")
    return Context(catalog=catalog, creator=creator, editor=editor, service=service)
