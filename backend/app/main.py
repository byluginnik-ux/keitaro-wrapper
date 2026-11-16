from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from strawberry.fastapi import GraphQLRouter

from app.graphql.context import Context, ServiceInfo
from app.graphql.schema import build_schema
from app.keitaro.client import KeitaroClient, create_http_client
from app.services.catalog import CatalogService
from app.services.creator import CreatorService
from app.services.editor import EditorService
from app.settings import Settings
from app.storage.factory import open_storage


def create_app(settings: Settings | None = None) -> FastAPI:
    """Assemble the application; run with `uvicorn --factory app.main:create_app`."""
    config = settings or Settings()  # pyright: ignore[reportCallIssue] — values come from the environment

    service = ServiceInfo(
        campaign_name_prefix=config.campaign_name_prefix,
        tracker_url=config.keitaro_base_url.rstrip("/"),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        async with (
            create_http_client(
                config.keitaro_base_url, config.keitaro_api_key.get_secret_value()
            ) as http,
            open_storage(config) as storage,
        ):
            keitaro = KeitaroClient(http)
            catalog = CatalogService(keitaro)
            app.state.catalog = catalog
            app.state.creator = CreatorService(
                keitaro, catalog, storage, name_prefix=config.campaign_name_prefix
            )
            app.state.editor = EditorService(keitaro, catalog, storage)
            yield

    def context(request: Request) -> Context:
        state = request.app.state
        return Context(
            catalog=state.catalog, creator=state.creator, editor=state.editor, service=service
        )

    app = FastAPI(
        title="Keitaro Wrapper", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    graphql = GraphQLRouter(
        build_schema(debug=config.debug),
        context_getter=context,
        graphql_ide="graphiql" if config.debug else None,
    )
    app.include_router(graphql, prefix="/graphql")

    @app.get("/health")
    async def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction] — registered by the decorator
        """Report that the process is up; used by compose and CI."""
        return {"status": "ok"}

    return app
