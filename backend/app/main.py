from fastapi import FastAPI

from app.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Assemble the application; run with `uvicorn --factory app.main:create_app`."""
    raise NotImplementedError
