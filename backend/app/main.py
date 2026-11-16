from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from strawberry.fastapi import GraphQLRouter

from app.graphql.context import Context
from app.graphql.schema import schema
from app.keitaro.client import KeitaroClient, create_http_client
from app.services.catalog import CatalogService
from app.services.creator import CreatorService
from app.settings import Settings
from app.storage.factory import open_storage


def create_app(settings: Settings | None = None) -> FastAPI:
    """Assemble the application; run with `uvicorn --factory app.main:create_app`."""
    config = settings or Settings()  # pyright: ignore[reportCallIssue] — values come from the environment

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        async with (
            create_http_client(config.keitaro_base_url, config.keitaro_api_key) as http,
            open_storage(config) as storage,
        ):
            keitaro = KeitaroClient(http)
            catalog = CatalogService(keitaro)
            app.state.catalog = catalog
            app.state.creator = CreatorService(
                keitaro, catalog, storage, name_prefix=config.campaign_name_prefix
            )
            yield

    def context(request: Request) -> Context:
        return Context(catalog=request.app.state.catalog, creator=request.app.state.creator)

    app = FastAPI(
        title="Keitaro Wrapper", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    graphql = GraphQLRouter(
        schema, context_getter=context, graphql_ide="graphiql" if config.debug else None
    )
    app.include_router(graphql, prefix="/graphql")

    @app.get("/health")
    async def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction] — registered by the decorator
        """Report that the process is up; used by compose and CI."""
        return {"status": "ok"}

    return app
