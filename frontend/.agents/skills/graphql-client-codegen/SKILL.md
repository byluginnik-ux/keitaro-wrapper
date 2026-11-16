---
name: graphql-client-codegen
description: Запросы BFF к GraphQL бэкенда — типы из пакета @keitaro-wrapper/contracts, документы запросов, генерация типов операций, клиент, разбор union-ответов. Использовать при добавлении или изменении запроса в frontend/server/graphql/, после новой версии контракта и при ошибках типов в ответах бэкенда.
---

# GraphQL-клиент BFF

## Источник типов

Пакет `@keitaro-wrapper/contracts` (`../contracts`, подключён как `link:`). Схему для генерации `codegen.yml` читает из пакета; базовые типы при необходимости импортируются из него и здесь не объявляются:

```ts
import type { Offer, Stream } from '@keitaro-wrapper/contracts'
```

Общий тип не тот — править `../contracts/schema.graphql` по скиллу `contract-change`, а не подправлять тип на месте.

## Документы и типы операций

- Один файл `.graphql` на экран или действие в `server/graphql/`: `editor.graphql`, `creator.graphql`.
- Типы операций генерируются у нас из документов и схемы пакета:
  ```
  corepack pnpm codegen      # schema из @keitaro-wrapper/contracts + server/graphql/**/*.graphql → server/graphql/operations.ts
  ```
  `operations.ts` лежит в git; CI проверяет, что повторная генерация ничего не меняет.
- Поля потока и оффера — фрагментами (`StreamFields`, `OfferFields`): каждая мутация редактора возвращает поток целиком.
- Запрашивать только то, что показывает экран. В union всегда запрашивать `__typename`.

## Клиент

Один тонкий клиент в `server/utils/graphql.ts` на `$fetch`: типизированный документ + переменные → данные. Без кэша и нормализации — BFF не хранит состояние.

## Разбор union

```ts
switch (result.__typename) {
  case 'Stream': return toStreamView(result)
  case 'ShareOverflow': throw apiError(422, 'share_overflow', result.message)
  // ...
  default: return assertNever(result)
}
```

`assertNever` обязателен: новый вариант union в контракте должен ломать проверку типов, а не молча теряться.

## Браузер

Клиентский код GraphQL не использует; типы контракта можно импортировать только как `import type`.
