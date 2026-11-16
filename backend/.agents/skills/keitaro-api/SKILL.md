---
name: keitaro-api
description: Работа с Keitaro Admin API в этом проекте — какие запросы нужны для кампаний, потоков, офферов и справочников, какие поля обязательны, как устроены фильтры и доли. Использовать при любой правке backend/app/keitaro/, при написании эталонных ответов для тестов и когда неясно, что Keitaro ждёт или возвращает. Не использовать для Click API и отчётов — они вне проекта.
---

# Keitaro Admin API

База: `{KEITARO_BASE_URL}/admin_api/v1`. Авторизация — заголовок `Api-Key`.
Полная схема — `https://admin-api.docs.keitaro.io/openapi.yaml`. Скачать во временную папку (`curl -sO`) и искать по пути запроса, а не читать целиком; в репозиторий не класть.

## Запросы проекта

| Задача | Запрос | Тело / ответ |
|--------|--------|--------------|
| Создать кампанию | `POST /campaigns` | `name`, `alias`, `type` (`position`\|`weight`), `group_id`, `traffic_source_id`, `domain_id` |
| Удалить кампанию | `DELETE /campaigns/{id}` | перемещает в архив |
| Создать поток | `POST /streams` | обязательны `campaign_id`, `schema`, `type`, `name`, `action_type` |
| Потоки кампании | `GET /campaigns/{id}/streams` | массив `Stream` с `offers[]`, `filters[]` |
| Изменить поток | `PUT /streams/{id}` | любые поля `StreamObject`; `offers[]` заменяет состав целиком |
| Офферы | `GET /offers` | массив `Offer` |
| Домены | `GET /domains` | |
| Создать домен | `POST /domains` | обязательно `name` (имя хоста); ответ — `Domain` с `id` |
| Группы | `GET /groups?type=campaigns` | |
| Источники | `GET /traffic_sources` | |
| Имена фильтров | `GET /stream_filters` | |
| Типы действий | `GET /streams_actions` | |

## Поток

```
schema:  landings | redirect | action
type:    forced | regular | default
filters: [{ name, mode: accept | reject, payload: [..] }]
offers:  [{ offer_id, share, state: active | disabled }]     # share — целый процент
```

- Поток-редирект: `schema: redirect`, URL в `action_payload`.
- Поток с офферами: `schema: landings`, список в `offers`.
- В ответе у оффера потока есть собственный `id` привязки — он не равен `offer_id`.

Проверено на живом трекере (эталоны — `backend/tests/fixtures/keitaro/`):

- редирект на URL: `type: regular`, `schema: redirect`, `action_type: http`, `action_payload: "<url>"`;
- фильтр страны: `{ name: "country", mode: "accept", payload: ["AU"] }` — коды ISO alpha-2 в верхнем регистре;
- поток с офферами: `type: regular`, `schema: landings`, `action_type: http`, `action_payload: ""`;
- порядок потоков задаёт `position` (1, 2, …);
- сумму долей Keitaro не проверяет;
- 404 на несуществующую сущность — страница HTML от nginx, не JSON;
- `GET /offers` отдаёт весь список без поиска и постраничности (сотни записей, ~160 КБ).

## Правила клиента

- Один класс `KeitaroClient` на `httpx.AsyncClient`; методы возвращают модели pydantic с `extra="ignore"`.
- Любой сбой → `KeitaroError(status, message)`. Тело ошибки Keitaro: `{"error": "..."}`.
- Повторы — только для GET.
- Ключ не логировать.

## Живой трекер

Кампании только с префиксом `test_bulygin_`. После проверки удалять. В тестах живой трекер не используется.
