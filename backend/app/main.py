from fastapi import FastAPI

app = FastAPI(title="Keitaro Wrapper", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
async def health() -> dict[str, str]:
    """Report that the process is up; used by compose and CI."""
    return {"status": "ok"}
