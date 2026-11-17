import asyncio
from collections.abc import AsyncGenerator, Awaitable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from strawberry.fastapi import GraphQLRouter

from app.graphql.context import Context, ServiceInfo
from app.graphql.schema import build_schema
from app.runtime import Runtime, open_runtime
from app.settings import Settings

# how long one part may take to answer a readiness check (R-OPS-04)
READY_TIMEOUT = 2.0


async def _answers(check: Awaitable[object]) -> bool:
    try:
        async with asyncio.timeout(READY_TIMEOUT):
            await check
    except Exception:  # noqa: BLE001 — whatever the part raised, it is not ready
        return False
    return True


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

    @app.get("/health/ready")
    async def ready(request: Request) -> JSONResponse:  # pyright: ignore[reportUnusedFunction] — registered by the decorator
        """Report whether the storage, the bus and the cache answer (R-OPS-04)."""
        runtime: Runtime = request.app.state.runtime
        parts = {
            "storage": runtime.storage.tasks.count_by_status(),
            "bus": runtime.bus.stats(),
            "cache": runtime.cache.ping(),
        }
        answered = await asyncio.gather(*(_answers(check) for check in parts.values()))
        failed = [name for name, ok in zip(parts, answered, strict=True) if not ok]
        if failed:
            return JSONResponse({"status": "unavailable", "failed": failed}, status_code=503)
        return JSONResponse({"status": "ready", "failed": []})

    return app
