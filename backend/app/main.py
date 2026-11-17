from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from strawberry.fastapi import GraphQLRouter

from app.graphql.context import Context, ServiceInfo
from app.graphql.schema import build_schema
from app.runtime import Runtime, open_runtime
from app.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Assemble the application; run with `uvicorn --factory app.main:create_app`."""
    config = settings or Settings()  # pyright: ignore[reportCallIssue] — values come from the environment

    service = ServiceInfo(
        campaign_name_prefix=config.campaign_name_prefix,
        tracker_url=config.keitaro_base_url.rstrip("/"),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        async with open_runtime(config) as runtime:
            app.state.runtime = runtime
            yield

    def context(request: Request) -> Context:
        runtime: Runtime = request.app.state.runtime
        return Context(
            catalog=runtime.catalog,
            creator=runtime.creator,
            editor=runtime.editor,
            publisher=runtime.publisher,
            tasks=runtime.tasks,
            service=service,
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
