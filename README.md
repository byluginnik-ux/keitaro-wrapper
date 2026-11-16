# Keitaro Wrapper

Обёртка над рекламным трекером Keitaro: создание кампаний с двумя потоками и редактор офферов в потоках.

```
браузер ──▶ frontend: Nuxt + Nitro (BFF) ──▶ backend: FastAPI + GraphQL ──▶ Keitaro Admin API
                                                        └──▶ Postgres (SQLAlchemy) | MongoDB
```

- `contracts/` — контракт GraphQL: `schema.graphql` и сгенерированные из него типы Python и TypeScript. Собирается в npm-пакет и пакет Python; единственное место правки общих типов.
- `backend/` — FastAPI, GraphQL (Strawberry), SQLAlchemy + Alembic; второй адаптер хранилища — MongoDB.
- `frontend/` — Nuxt (Vue 3 + TypeScript); сервер Nitro — BFF между браузером и бэкендом.
- `docs/SPEC.md` — техническое задание; `docs/FEATURES.md` — список фич и их статус; `docs/AI_USAGE.md` — как использовались ИИ-агенты.

## Запуск

Нужен Docker с Compose.

```
cp .env.example .env        # вписать KEITARO_API_KEY из админки Keitaro
docker compose up --build
```

Интерфейс — http://127.0.0.1:3000 (порт меняется переменной `FRONTEND_PORT`). Бэкенд наружу не открыт: к нему обращается только BFF.

## Миграции

Схема базы меняется только миграциями Alembic. Появятся вместе с хранилищем (фича F03); команды:

```
docker compose run --rm backend alembic upgrade head      # применить
docker compose run --rm backend alembic downgrade -1      # откатить последнюю
```

## Разработка

Контракт: `contracts/scripts/generate.sh` после правки `schema.graphql`, `contracts/scripts/check.sh` для проверки.

| | backend | frontend |
|---|---------|----------|
| Зависимости | `uv sync` | `corepack pnpm install` |
| Запуск | `uv run uvicorn app.main:app --reload` | `corepack pnpm dev` |
| Тесты | `uv run pytest -q` | `corepack pnpm test` |
| Линтеры | `uv run ruff check . && uv run ruff format --check .` | `corepack pnpm lint` |
| Типы | `uv run pyright` | `corepack pnpm typecheck` |

Хуки перед коммитом (линтеры, поиск секретов, формат сообщения):

```
uvx pre-commit install
```

Разработка идёт от тестов: коммит с падающим тестом, затем коммит с реализацией. Правила — в `AGENTS.md`.

## Агенты

Правила и скиллы для ИИ-агентов лежат в репозитории: общие — `AGENTS.md` и `.agents/skills/`, для частей — `contracts/AGENTS.md`, `backend/AGENTS.md`, `frontend/AGENTS.md` и их `.agents/skills/`.
