from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from pymongo import AsyncMongoClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.settings import Settings
from app.storage.memory import create_memory_storage
from app.storage.mongo.adapter import create_mongo_storage, prepare
from app.storage.ports import Storage
from app.storage.sqlalchemy.adapter import create_sqlalchemy_storage


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the engine of the configured database with its pool (R-OPS-05)."""
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )


def create_mongo_client(settings: Settings) -> AsyncMongoClient[dict[str, Any]]:
    """Build the client of the configured MongoDB with its pool (R-OPS-05)."""
    return AsyncMongoClient(
        settings.mongo_url,
        uuidRepresentation="standard",
        tz_aware=True,
        maxPoolSize=settings.mongo_max_pool_size,
    )


@asynccontextmanager
async def open_storage(settings: Settings) -> AsyncGenerator[Storage]:
    """Open the storage chosen by STORAGE_BACKEND and close it with the process (R-ST-03)."""
    match settings.storage_backend:
        case "memory":
            yield create_memory_storage()
        case "mongo":
            client = create_mongo_client(settings)
            try:
                database = client[settings.mongo_database]
                await prepare(database)
                yield create_mongo_storage(database)
            finally:
                await client.close()
        case "postgres":
            engine = create_engine(settings)
            try:
                yield create_sqlalchemy_storage(engine)
            finally:
                await engine.dispose()
