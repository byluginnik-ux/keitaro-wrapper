# Keitaro Wrapper — правила для агентов

## Карта

| Путь | Что там | Правила |
|------|---------|---------|
| `docs/SPEC.md` | Техническое задание, требования `R-xx`, сценарии `S1`–`S8` | источник истины |
| `docs/FEATURES.md` | Порядок фич и их статус | обновлять при закрытии фичи |
| `contracts/` | Схема GraphQL и сгенерированные типы Python и TypeScript; публикуемый пакет | `contracts/AGENTS.md` |
| `backend/` | FastAPI, GraphQL, клиент Keitaro, хранилище | `backend/AGENTS.md` |
| `frontend/` | Nuxt: интерфейс и BFF на Nitro | `frontend/AGENTS.md` |

`backend/` и `frontend/` не импортируют код друг друга; обе зависят только от `contracts/`. Общий тип меняется в одном месте — `contracts/schema.graphql` (скилл `contract-change`), и только потом в частях.

## Порядок работы

1. Найти требование в `docs/SPEC.md`. Нет требования — сначала правка ТЗ отдельным коммитом `docs(spec): …`.
2. Написать падающий тест, закоммитить (`test(...)`).
3. Написать минимальную реализацию, закоммитить (`feat(...)` или `fix(...)`).
4. Заполнить строку в матрице SPEC.md и статус в FEATURES.md.

Подробности — скиллы `tdd-cycle`, `clean-git-history`, `spec-traceability` в `.agents/skills/`.

## Запреты

- Не коммитить `.env`, ключи и пароли. Ключ Keitaro живёт только в окружении.
- Не обращаться к настоящему Keitaro из тестов.
- Не создавать в Keitaro кампании без префикса `test_bulygin_`; созданные при проверке — удалять.
- Не переносить предметную логику в BFF или в компоненты.
- Не делать `git push`, `git push --force` и правку опубликованной истории без прямого указания человека.

## Скиллы

Общие лежат в `.agents/skills/` (ссылка `.claude/skills`). Скиллы частей — в `contracts/.agents/skills/`, `backend/.agents/skills/` и `frontend/.agents/skills/`.

Установленные у разработчика глобально и полезные здесь (в репозиторий не копируются):
`graphify` — граф кода для вопросов об архитектуре; `pretty-mermaid` — диаграммы;
плагин `agent-skills`: `spec-driven-development`, `test-driven-development`, `git-workflow-and-versioning`.

## MCP

`.mcp.json`: `context7` — актуальная документация библиотек. Перед использованием незнакомого API библиотеки сверяться с ней, а не с памятью.
