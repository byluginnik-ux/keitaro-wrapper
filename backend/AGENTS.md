# Backend — правила для агентов

FastAPI + GraphQL (Strawberry) + SQLAlchemy. Общие правила — в `../AGENTS.md`, требования — в `../docs/SPEC.md`.

## Команды

```
uv sync                              # зависимости
uv run pytest -x -q                  # тесты
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run uvicorn app.main:app --reload # запуск, http://127.0.0.1:8000/health
```

Перед коммитом все четыре проверки зелёные.

## Слои

`graphql → services → storage.ports | keitaro`. Подробно — скилл `fastapi-layers`.

## Скиллы (`.agents/skills/`)

| Скилл | Когда |
|-------|-------|
| `fastapi-layers` | куда положить код, границы слоёв |
| `typed-python` | типы, pydantic, dataclass, ошибки pyright и ruff |
| `graphql-strawberry` | резолверы поверх типов контракта, ошибки-union, соответствие схеме |
| `keitaro-api` | запросы и поля Admin API |
| `storage-adapters` | интерфейсы, SQLAlchemy, Alembic, MongoDB |
| `share-math` | пересчёт долей |
| `pytest-patterns` | раскладка и приёмы тестов |
| `api-security-testing`, `owasp-top-10-testing`, `find-security-vulnerabilities-in-code` | проверка безопасности перед сдачей (нужен CLI `strix`) |

## Правила части

- Бэкенд лаконичный: резолвер вызывает один метод сервиса; абстракция появляется только при двух реализациях или ради подмены в тестах.
- Типы GraphQL берутся из пакета `keitaro_contracts` и здесь не объявляются. Нужен новый тип или поле — сначала правка `../contracts/schema.graphql` (скилл `contract-change`), потом резолвер.
- Изменил модели SQLAlchemy — миграция Alembic в том же коммите; тот же контракт должен пройти адаптер MongoDB.
- Тесты не ходят в сеть.
