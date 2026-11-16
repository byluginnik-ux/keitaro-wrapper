# Keitaro Wrapper

Обёртка над рекламным трекером Keitaro: создание кампаний с двумя потоками и редактор офферов в потоках.

- `backend/` — FastAPI, GraphQL (Strawberry), SQLAlchemy + Alembic, второй адаптер хранилища — MongoDB.
- `frontend/` — Nuxt (Vue 3 + TypeScript); сервер Nitro работает как BFF между браузером и бэкендом.
- `docs/SPEC.md` — техническое задание, `docs/FEATURES.md` — список фич и порядок работ.

Инструкция по запуску и миграциям появится вместе с каркасом (фича F00).
