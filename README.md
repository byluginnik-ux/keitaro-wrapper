# Keitaro Wrapper

Обёртка над рекламным трекером Keitaro: создание кампаний с двумя потоками и редактор офферов в потоках с черновиком, пересчётом долей и публикацией в трекер.

- [Запуск](#запуск) · [Архитектура](#архитектура) · [Что готово](#что-готово) · [Разработка](#разработка)
- Техническое задание — [docs/SPEC.md](docs/SPEC.md); архитектура подробно — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); порядок показа — [docs/DEMO.md](docs/DEMO.md); как использовались ИИ-агенты — [docs/AI_USAGE.md](docs/AI_USAGE.md).

## Запуск

### С настоящим Keitaro

Нужен Docker с Compose и ключ Admin API.

```
cp .env.example .env        # вписать KEITARO_API_KEY из админки Keitaro
docker compose up --build
```

Интерфейс — http://127.0.0.1:3000 (порт меняется переменной `FRONTEND_PORT`). Миграции базы применяются сами до старта бэкенда. Бэкенд наружу не открыт: к нему обращается только BFF.

Сервис создаёт кампании только с префиксом `test_bulygin_` (`CAMPAIGN_NAME_PREFIX`).

### Без Keitaro и без Docker

Трекер заменяет поддельный из тестов, данные живут в памяти. Нужны `uv` и Node.js с corepack. Три терминала:

```
# 1. поддельный трекер
cd backend && uv sync
uv run uvicorn tests.fake_tracker:app --port 8791

# 2. бэкенд
cd backend
KEITARO_BASE_URL=http://127.0.0.1:8791 KEITARO_API_KEY=fake-key STORAGE_BACKEND=memory \
  uv run uvicorn --factory app.main:create_app --port 8792

# 3. интерфейс
cd frontend && corepack pnpm install
NUXT_BACKEND_GRAPHQL_URL=http://127.0.0.1:8792/graphql corepack pnpm dev
```

Интерфейс — http://localhost:3000. Готовую кампанию с двумя потоками для редактора создаёт команда ниже; `campaignId` из ответа вводится на главной странице.

```
curl -X POST http://127.0.0.1:8791/__test/campaign -H 'content-type: application/json' -d '{}'
```

### Страницы

| Страница | Что на ней |
|----------|------------|
| `/` | Кампании сервиса; открыть любую кампанию трекера по её ID |
| `/create` | Создаватор: название с префиксом, страна, оффер, домен (существующий или новый), группа, источник. Создаёт кампанию и два потока: первый уводит выбранную страну на Google, второй ведёт на оффер. При сбое кампания удаляется |
| `/campaigns/<id>` | Редактор офферов в потоках: добавить, удалить, вернуть, закрепить долю. Изменения копятся в черновике и уходят в Keitaro кнопкой «Опубликовать»; «Отменить» возвращает опубликованное состояние |

### Переменные окружения

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `KEITARO_BASE_URL` | `https://tlgk.host` | адрес трекера |
| `KEITARO_API_KEY` | — | ключ Admin API; без него бэкенд не стартует |
| `CAMPAIGN_NAME_PREFIX` | `test_bulygin_` | обязательный префикс имён кампаний |
| `STORAGE_BACKEND` | `postgres` | `postgres`, `mongo` или `memory` |
| `FRONTEND_PORT` | `3000` | порт интерфейса на хосте |
| `DEBUG` | `false` | GraphiQL и интроспекция схемы на `/graphql` бэкенда |

## Архитектура

```
браузер ──▶ frontend: Nuxt + Nitro (BFF) ──▶ backend: FastAPI + GraphQL ──▶ Keitaro Admin API
                    │                                   │
                    │                                   └──▶ хранилище: Postgres | MongoDB
                    └────────▶ contracts: schema.graphql + типы ◀────────┘
```

- `contracts/` — контракт GraphQL: `schema.graphql` и сгенерированные из него типы Python и TypeScript. Собирается в npm-пакет и пакет Python; единственное место правки общих типов.
- `backend/` — FastAPI, GraphQL (Strawberry), SQLAlchemy + Alembic; второй адаптер хранилища — MongoDB. Вся предметная логика здесь: слои `graphql → services → порты хранилища | шлюз Keitaro`.
- `frontend/` — Nuxt (Vue 3 + TypeScript). Nitro — серверная часть самого Nuxt, а не отдельный сервис: маршруты `frontend/server/api/*` работают в том же процессе, что и страницы, и служат BFF между браузером и бэкендом. Логики в BFF нет.

Основные решения:

- **Черновик и снимок.** Поток хранит текущие значения и снимок того, что лежит в Keitaro; «не опубликовано» вычисляется сравнением. Удалённый оффер остаётся со статусом `removed` и долей 0.
- **Доли** считает чистая функция: закреплённые сохраняются, остаток делится поровну, сумма всегда 100.
- **Хранилище за портом.** Postgres, MongoDB и память проходят один набор контрактных тестов; выбор — переменной `STORAGE_BACKEND`.
- **Конкурентная запись.** У потока есть версия, запись условная; правка из устаревшего окна получает отказ с актуальным потоком. Одно действие — одна транзакция вместе с журналом.
- **Основа событийной записи.** Задачи с ключом идемпотентности, transactional outbox и шина сообщений (память, RabbitMQ) с повторами и очередью отказов.

Схемы, слои и модель подробно — в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Что готово

Полный список со статусами — [docs/FEATURES.md](docs/FEATURES.md).

| Готово | В работе |
|--------|----------|
| Создаватор и редактор целиком: бэкенд, BFF, интерфейс, сценарии S1–S8 из ТЗ | Публикация потока и создание кампании задачами с итоговым событием (F17, F18) |
| Хранилище на Postgres и MongoDB, миграции | Страница «Задачи»: статусы, отмена, повтор, состояние очереди (F19) |
| Версии потока, конфликт двух окон, транзакции (F13, F14) | Redis: общий кэш справочников и ограничитель обращений к Keitaro (F20) |
| Задачи и outbox в хранилище, шина сообщений и отправитель (F15, F16) | Эксплуатация: готовность, масштабирование, нагрузочный сценарий (F21) |

Публикация и создание кампании сейчас выполняются синхронно в запросе; шина и outbox покрыты тестами, но к ним ещё не подключены.

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

Тесты хранилища и шины на настоящих базах и брокере (без них пропускаются с причиной, в CI пропуск запрещён):

```
docker compose --profile test up -d --wait db-test mongo-test rabbitmq-test
export TEST_DATABASE_URL=postgresql+asyncpg://keitaro:keitaro@127.0.0.1:55432/keitaro_test
export TEST_MONGO_URL="mongodb://127.0.0.1:57017/?directConnection=true"
export TEST_RABBITMQ_URL="amqp://guest:guest@127.0.0.1:55672/"
uv run pytest -q
```

### Хранилище

`STORAGE_BACKEND` в `.env` выбирает реализацию; сервисы и GraphQL от неё не зависят, все адаптеры проходят один набор тестов (`backend/tests/storage/`).

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
