---
name: graphql-strawberry
description: Схема GraphQL на Strawberry внутри FastAPI — типы, запросы, мутации, предметные ошибки через union, выгрузка schema.graphql. Использовать при любой правке backend/app/graphql/ и при изменении контракта с фронтом. Перед использованием незнакомой возможности Strawberry сверяться с документацией через context7.
---

# GraphQL в проекте

## Устройство

- Один объект `schema = strawberry.Schema(query=Query, mutation=Mutation)` в `app/graphql/schema.py`.
- Подключение: `GraphQLRouter(schema, context_getter=...)` на `/graphql`. Контекст несёт сервисы.
- Типы — `@strawberry.type` с аннотациями Python; имена полей в схеме — camelCase (делает Strawberry).
- Тип GraphQL строится из доменной модели функцией `from_domain`, а не наследованием.

## Контракт

`backend/schema.graphql` лежит в git и выгружается командой:

```
uv run strawberry export-schema app.graphql.schema:schema > schema.graphql
```

Тест сравнивает файл с текущей схемой. Изменил типы — перевыгрузи файл в том же коммите. Фронт генерирует из него типы, поэтому удаление или переименование поля — ломающее изменение: сначала правка BFF.

## Ошибки

Предметные ошибки — часть схемы, а не `errors[]`:

```python
@strawberry.type
class ShareOverflow:
    message: str
    pinned_total: int

StreamResult = Annotated[Stream | ShareOverflow | OfferAlreadyInStream | DraftNotPublished | KeitaroFailure,
                         strawberry.union("StreamResult")]
```

- Каждая мутация редактора возвращает `StreamResult`: поток целиком или типизированную ошибку.
- `errors[]` остаётся для сбоев, которых клиент не ждёт (ошибка в коде, недоступная база).
- У каждого типа ошибки есть `message` для показа человеку.

## Запросы и мутации

- Запросы: `campaigns`, `campaign(id)`, `offers(search)`, `domains`, `groups`, `trafficSources`, `countries`.
- Мутации: `createCampaign`, `fetchStreams`, `addOffer`, `removeOffer`, `bringBackOffer`, `setShare`, `unpinShare`, `cancelStream`, `pushStream`.
- Вход мутации — один `@strawberry.input`.
- ID наружу — `strawberry.ID`; ID Keitaro — отдельное целое поле `keitaroId`.

## Тесты

Через `schema.execute(...)` с подставленным контекстом: проверяется ответ GraphQL, а не вызовы сервиса.
