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

Схема базы меняется только миграциями Alembic (`backend/alembic/versions/`). При `docker compose up` их применяет сервис `migrate` до старта бэкенда. Вручную:

```
docker compose run --rm migrate                               # применить все (alembic upgrade head)
docker compose run --rm migrate alembic downgrade -1          # откатить последнюю
docker compose run --rm migrate alembic current               # текущая версия схемы
```

Новая миграция после изменения моделей в `backend/app/storage/sqlalchemy/tables.py`:

```
docker compose --profile test up -d db-test
cd backend
export DATABASE_URL=postgresql+asyncpg://keitaro:keitaro@127.0.0.1:55432/keitaro_test
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "что изменилось"    # прочитать и поправить файл
uv run alembic check                                          # модели и миграции совпадают
```

## Разработка

Контракт: `contracts/scripts/generate.sh` после правки `schema.graphql`, `contracts/scripts/check.sh` для проверки.

| | backend | frontend |
|---|---------|----------|
| Зависимости | `uv sync` | `corepack pnpm install` |
| Запуск | `uv run uvicorn --factory app.main:create_app --reload` | `corepack pnpm dev` |
| Тесты | `uv run pytest -q` | `corepack pnpm test` |
| Линтеры | `uv run ruff check . && uv run ruff format --check .` | `corepack pnpm lint` |
| Типы | `uv run pyright` | `corepack pnpm typecheck` |

Тесты хранилища на настоящей базе (без неё они пропускаются с причиной, в CI пропуск запрещён):

```
docker compose --profile test up -d db-test
TEST_DATABASE_URL=postgresql+asyncpg://keitaro:keitaro@127.0.0.1:55432/keitaro_test uv run pytest -q
```

Хуки перед коммитом (линтеры, поиск секретов, формат сообщения):

```
uvx pre-commit install
```

Разработка идёт от тестов: коммит с падающим тестом, затем коммит с реализацией. Правила — в `AGENTS.md`.

## Агенты

Правила и скиллы для ИИ-агентов лежат в репозитории: общие — `AGENTS.md` и `.agents/skills/`, для частей — `contracts/AGENTS.md`, `backend/AGENTS.md`, `frontend/AGENTS.md` и их `.agents/skills/`.
