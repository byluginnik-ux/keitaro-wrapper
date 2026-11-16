from dataclasses import dataclass

from strawberry.fastapi import BaseContext

from app.services.catalog import CatalogService


@dataclass
class Context(BaseContext):
    """Services a resolver may call; built once per request."""

    catalog: CatalogService
