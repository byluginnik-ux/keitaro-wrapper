from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine

from app.settings import Settings
from app.storage.memory import create_memory_storage
from app.storage.ports import Storage
from app.storage.sqlalchemy.adapter import create_sqlalchemy_storage


@asynccontextmanager
async def open_storage(settings: Settings) -> AsyncGenerator[Storage]:
    """Open the storage chosen by STORAGE_BACKEND and close it with the process (R-ST-03)."""
    if settings.storage_backend == "memory":
        yield create_memory_storage()
        return
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        yield create_sqlalchemy_storage(engine)
    finally:
        await engine.dispose()
