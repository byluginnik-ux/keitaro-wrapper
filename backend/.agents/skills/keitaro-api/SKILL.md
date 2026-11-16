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

Точные значения `action_type` и имя фильтра страны брать из эталонных ответов `backend/tests/fixtures/keitaro/` (сняты с живого трекера), а не из памяти.

## Правила клиента

- Один класс `KeitaroClient` на `httpx.AsyncClient`; методы возвращают модели pydantic с `extra="ignore"`.
- Любой сбой → `KeitaroError(status, message)`. Тело ошибки Keitaro: `{"error": "..."}`.
- Повторы — только для GET.
- Ключ не логировать.

## Живой трекер

Кампании только с префиксом `test_bulygin_`. После проверки удалять. В тестах живой трекер не используется.
