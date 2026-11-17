# Keitaro Wrapper

Обёртка над рекламным трекером Keitaro: создание кампаний с двумя потоками и редактор офферов в потоках.

```
браузер ──▶ frontend: Nuxt + Nitro (BFF) ──▶ backend: FastAPI + GraphQL ──▶ Keitaro Admin API
                                                        └──▶ Postgres (SQLAlchemy) | MongoDB
```

- `contracts/` — контракт GraphQL: `schema.graphql` и сгенерированные из него типы Python и TypeScript. Собирается в npm-пакет и пакет Python; единственное место правки общих типов.
- `backend/` — FastAPI, GraphQL (Strawberry), SQLAlchemy + Alembic; второй адаптер хранилища — MongoDB.
- `frontend/` — Nuxt (Vue 3 + TypeScript). Nitro — серверная часть самого Nuxt, а не отдельный сервис: маршруты `frontend/server/api/*` работают в том же процессе и контейнере, что и страницы, и служат BFF между браузером и бэкендом.
- `docs/SPEC.md` — техническое задание; `docs/FEATURES.md` — список фич и их статус; `docs/AI_USAGE.md` — как использовались ИИ-агенты.

## Запуск

Нужен Docker с Compose.

```
cp .env.example .env        # вписать KEITARO_API_KEY из админки Keitaro
docker compose up --build
```

Интерфейс — http://127.0.0.1:3000 (порт меняется переменной `FRONTEND_PORT`). Бэкенд наружу не открыт: к нему обращается только BFF.

| Страница | Что на ней |
|----------|------------|
| `/` | Кампании сервиса; открыть любую кампанию трекера по её ID |
| `/create` | Создаватор: название с префиксом `test_bulygin_`, страна, оффер, домен (существующий или новый), группа, источник. Создаёт кампанию и два потока; при сбое кампания удаляется |
| `/campaigns/<id>` | Редактор офферов в потоках: добавить, удалить, вернуть, закрепить долю; изменения копятся в черновике и уходят в Keitaro кнопкой «Опубликовать» |

Порядок показа — в [docs/DEMO.md](docs/DEMO.md).

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

Сквозные сценарии S1–S8 из ТЗ идут в браузере на всём сервисе; Keitaro заменён поддельным трекером `backend/tests/fake_tracker.py`, в настоящий ничего не пишется:

```
cd frontend
corepack pnpm exec playwright install chromium    # один раз
corepack pnpm test:e2e
```

Тесты хранилища на настоящих базах (без них пропускаются с причиной, в CI пропуск запрещён):

```
docker compose --profile test up -d --wait db-test mongo-test rabbitmq-test
export TEST_DATABASE_URL=postgresql+asyncpg://keitaro:keitaro@127.0.0.1:55432/keitaro_test
export TEST_MONGO_URL="mongodb://127.0.0.1:57017/?directConnection=true"
export TEST_RABBITMQ_URL="amqp://guest:guest@127.0.0.1:55672/"
uv run pytest -q
```

### Хранилище

`STORAGE_BACKEND` в `.env` выбирает реализацию; сервисы и GraphQL от неё не зависят, оба адаптера проходят один набор тестов (`backend/tests/storage/test_contract.py`).

| Значение | Что нужно | Запуск |
|----------|-----------|--------|
| `postgres` (по умолчанию) | Postgres, миграции Alembic | `docker compose up --build` |
| `mongo` | MongoDB одним узлом replica set (нужен транзакциям), индексы создаются при старте | `STORAGE_BACKEND=mongo docker compose --profile mongo up --build` |
| `memory` | ничего, данные живут до перезапуска | — |

### Защита API

- Браузер обращается только к `/api/*` своего сервера; адрес бэкенда и ключ Keitaro в него не попадают.
- Бэкенд наружу не опубликован (в `compose.yaml` у него нет проброса порта).
- GraphiQL и интроспекция схемы включаются только при `DEBUG=true`; запрос ограничен по числу лексем и псевдонимов.
- Ключ Keitaro читается из окружения и хранится как секретное значение: в печати настроек его нет.

Хуки перед коммитом (линтеры, поиск секретов, формат сообщения):

```
uvx pre-commit install
```

Разработка идёт от тестов: коммит с падающим тестом, затем коммит с реализацией. Правила — в `AGENTS.md`.

## Агенты

Правила и скиллы для ИИ-агентов лежат в репозитории: общие — `AGENTS.md` и `.agents/skills/`, для частей — `contracts/AGENTS.md`, `backend/AGENTS.md`, `frontend/AGENTS.md` и их `.agents/skills/`.
