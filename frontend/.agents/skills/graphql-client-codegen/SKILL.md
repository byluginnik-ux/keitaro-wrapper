---
name: graphql-client-codegen
description: Запросы BFF к GraphQL бэкенда — документы, генерация типов из backend/schema.graphql, клиент, разбор union-ответов. Использовать при добавлении или изменении запроса в frontend/server/graphql/, после изменения схемы бэкенда и при ошибках типов в ответах бэкенда.
---

# GraphQL-клиент BFF

## Источник типов

`../backend/schema.graphql` — единственный контракт. Типы генерируются, руками не пишутся:

```
corepack pnpm codegen      # graphql-codegen: schema.graphql + server/graphql/**/*.graphql → server/graphql/generated.ts
```

`generated.ts` лежит в git; CI проверяет, что повторная генерация ничего не меняет. Схема изменилась — перегенерировать в том же коммите, что и правка запросов.

## Документы

- Один файл `.graphql` на экран или действие: `editor.graphql`, `creator.graphql`.
- Поля потока и оффера описаны фрагментами (`StreamFields`, `OfferFields`) и переиспользуются во всех мутациях редактора: каждая возвращает поток целиком.
- Запрашивать только то, что показывает экран.
- В union всегда запрашивать `__typename`.

## Клиент

Один тонкий клиент в `server/utils/graphql.ts` на `$fetch`: типизированный документ + переменные → данные. Без кэша и без нормализации — BFF не хранит состояние.

## Разбор union

```ts
switch (result.__typename) {
  case 'Stream': return toStreamView(result)
  case 'ShareOverflow': throw apiError(422, 'share_overflow', result.message)
  // ...
  default: return assertNever(result)
}
```

`assertNever` обязателен: новый тип ошибки в схеме должен ломать проверку типов, а не молча теряться.

## Браузер

Клиентский код GraphQL не использует и сгенерированные типы не импортирует.
