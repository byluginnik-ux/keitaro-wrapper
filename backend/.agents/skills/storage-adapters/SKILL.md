---
name: storage-adapters
description: Хранилище бэкенда — интерфейсы в storage/ports.py и два адаптера, SQLAlchemy (Postgres, Alembic) и MongoDB, с переключением через STORAGE_BACKEND. Использовать при правке backend/app/storage/, добавлении поля или сущности, создании миграции и при расхождении поведения адаптеров.
---

# Хранилище

## Интерфейсы

`storage/ports.py` описывает репозитории в терминах доменных моделей: `CampaignRepository`, `StreamRepository`, `AuditLog`. `Storage` даёт их в двух видах:

- `storage.campaigns`, `storage.streams`, `storage.audit` — каждый вызов фиксируется сам; для чтения и одиночной записи;
- `async with storage.transaction() as work:` — единица работы (`UnitOfWork`): всё записанное через `work.*` применяется вместе или не применяется (R-ST-06). Внутри блока — только хранилище, без запросов к Keitaro.

Сервисы видят только `ports` и `storage/errors.py`. Адаптер выбирается в `storage/factory.py` по `settings.storage_backend`.

## Условная запись потока

- У потока есть `version` — сколько раз он записан; у нового 0 (R-CC-01).
- `streams.save(stream)` пишет, только если версия в хранилище равна `stream.version`, и возвращает поток с версией на 1 больше. Дальше работать с возвращённым значением, а не с переданным.
- Отказы (`storage/errors.py`): `StaleStreamError` — поток изменён после чтения; `DuplicateError` — запись с таким ID или ID Keitaro уже есть; обе — `StorageConflictError`, сервис превращает их в предметный отказ или перечитывает и повторяет. `MissingParentError` — нет кампании потока.
- Безусловной записи потока нет и добавлять её нельзя: она возвращает потерю правок.

## Задачи и outbox

- `tasks.add(task)` — новая задача; известный ID — `DuplicateError`: ID выдаёт клиент, это ключ идемпотентности (R-TK-03).
- `tasks.save(task, was=статус)` — переход, только если задача сейчас в статусе `was`; иначе `StaleTaskError` (R-TK-02). Так обработчик и отмена не выполняют одну задачу дважды.
- `outbox.put(message)` вызывается только внутри `storage.transaction()` вместе с изменением данных (R-EV-01).
- `outbox.claim(limit, now, lease)` берёт самые старые неотправленные сообщения в аренду; `mark_sent` закрывает их. Postgres — `FOR UPDATE SKIP LOCKED`, Mongo — `find_one_and_update` по одному (R-EV-02).
- Части задачи, которые обе базы хранят как JSON (отказ, шаги), кодирует `storage/codec.py`.

## Правило трёх адаптеров

Любое изменение интерфейса делается одним заходом в `ports.py`, `memory.py`, `sqlalchemy/`, `mongo/` и покрывается контрактным тестом в `tests/storage/test_contract.py`, который идёт на всех адаптерах (фикстура `storage`). Гонки сервисов поверх хранилища — `tests/storage/test_concurrent_edits.py`. Поведение, не описанное контрактным тестом, считается неопределённым.

## SQLAlchemy

- Версия 2: `DeclarativeBase`, `Mapped[...]`, `mapped_column`, асинхронный движок (`asyncpg`).
- Строки ORM не покидают адаптер: наружу — доменные модели. Запись идёт выражениями `insert`/`update`/`delete`, ORM — только для чтения.
- Репозиторий получает «область» (`Scope`) — откуда брать сессию: собственная транзакция (`sessions.begin`) или общая сессия единицы работы.
- Условная запись — `UPDATE … WHERE id = :id AND version = :v`: блокировка строки заставляет второго писателя ждать и увидеть новую версию. Потоки пишутся в порядке ID, чтобы две пачки не ждали друг друга.
- Схема меняется только миграцией:
  ```
  uv run alembic revision --autogenerate -m "add stream offers"
  uv run alembic upgrade head
  ```
  Сгенерированную миграцию прочитать и поправить; `downgrade` обязателен. Миграция идёт одним коммитом с изменением моделей.

## MongoDB

- `pymongo.AsyncMongoClient`. Поток хранится документом с вложенным массивом привязок офферов.
- Условная запись — `replace_one({_id, version})`; новый поток — `insert_one`.
- Единица работы — многодокументная транзакция, поэтому нужен replica set (в compose — один узел). Конфликт записи двух транзакций (`WriteConflict`) адаптер отдаёт как `StorageConflictError`.
- Индексы создаёт `prepare()` при старте, миграций нет.

## Идентификаторы

Наш ID — UUID, создаётся в сервисе, а не базой. ID кампании и потока выводятся из их ID в Keitaro (`campaign_uuid`, `stream_uuid` в `services/models.py`): две одновременные загрузки сходятся к одной записи (R-CC-04). ID Keitaro — отдельное поле с уникальным индексом.
