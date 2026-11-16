from sqlalchemy.ext.asyncio import AsyncEngine

from app.storage.ports import Storage


def create_sqlalchemy_storage(engine: AsyncEngine) -> Storage:
    """Persist through SQLAlchemy; the schema is owned by Alembic migrations (R-ST-02)."""
    raise NotImplementedError
