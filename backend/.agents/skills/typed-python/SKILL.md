---
name: typed-python
description: Типизация и стиль Python в бэкенде — pyright strict, ruff, pydantic v2, dataclass, Protocol. Использовать при написании и ревью любого файла .py в backend/, при ошибках pyright или ruff и перед желанием поставить type: ignore или Any.
---

# Типизированный Python

Проверки: `uv run ruff check . && uv run ruff format --check . && uv run pyright`. Обе — без ошибок и без предупреждений.

## Правила

- Аннотации у всех параметров и возвращаемых значений, включая тесты и фикстуры.
- `Any` и `# type: ignore` — только с кодом правила и причиной в той же строке: `# pyright: ignore[reportUnknownMemberType] — у библиотеки нет типов`.
- Современный синтаксис: `list[int]`, `X | None`, `type Alias = ...`, `Self`, `override`.
- `from __future__ import annotations` не нужен.

## Чем моделировать

| Что | Чем |
|-----|-----|
| Данные извне (Keitaro, окружение) | `pydantic.BaseModel` / `BaseSettings`, `model_config = ConfigDict(extra="ignore", frozen=True)` |
| Доменные модели | `@dataclass(frozen=True, slots=True)` |
| Перечисления | `enum.StrEnum` |
| Идентификаторы разной природы | `NewType` (`OfferId`, `StreamId`) — чтобы не перепутать ID Keitaro и наш |
| Интерфейсы | `typing.Protocol` |
| Словари с известными ключами | не использовать; завести модель |

## Ошибки

- Свои исключения наследуются от одного базового `DomainError` с полем `code`.
- Не ловить голый `Exception`, кроме границы приложения.
- Не возвращать `None` как признак ошибки.

## Асинхронность

- Ввод-вывод — `async`. Чистые функции — синхронные.
- Не вызывать блокирующий код в корутине.
- Ресурсы (клиент HTTP, движок базы) создаются в `lifespan` и закрываются там же.

## Стиль

- Функция делает одно дело и помещается на экран.
- Комментарий объясняет «почему», а не «что». Строка документации — у публичных функций сервисов, со ссылкой на требование (`R-SH-04`).
- Имена — по-английски, предметные: `pinned_total`, а не `tmp_sum`.
