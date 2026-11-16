from dataclasses import dataclass

from strawberry.fastapi import BaseContext

from app.services.catalog import CatalogService
from app.services.creator import CreatorService
from app.services.editor import EditorService


@dataclass
class Context(BaseContext):
    """Services a resolver may call; built once per request."""

    catalog: CatalogService
    creator: CreatorService
    editor: EditorService
