# Build context is the repository root: the backend depends on ../contracts.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 PYTHONUNBUFFERED=1

COPY contracts /srv/contracts
WORKDIR /srv/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-install-project
COPY backend/app ./app

RUN useradd --system --uid 10001 app
USER app
EXPOSE 8000
CMD ["/srv/backend/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
