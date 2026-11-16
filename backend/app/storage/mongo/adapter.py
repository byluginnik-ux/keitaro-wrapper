from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.storage.ports import Storage

type Database = AsyncDatabase[dict[str, Any]]


async def prepare(database: Database) -> None:
    """Create the indexes the adapter relies on; safe to repeat."""
    raise NotImplementedError


def create_mongo_storage(database: Database) -> Storage:
    """Persist in MongoDB: a stream is one document together with its offers (R-ST-05)."""
    raise NotImplementedError
