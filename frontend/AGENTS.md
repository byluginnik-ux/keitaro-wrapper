# Frontend — правила для агентов

Nuxt 4 (Vue 3 + TypeScript). Сервер Nitro — BFF между браузером и бэкендом. Общие правила — в `../AGENTS.md`, требования — в `../docs/SPEC.md` (раздел 8), стиль — в `DESIGN.md`.

## Команды

```
corepack pnpm install
corepack pnpm dev          # http://localhost:3000
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm test
```

Перед коммитом `lint`, `typecheck`, `test` зелёные.

## Раскладка

```
app/      страницы, компоненты, composables — обращается только к /api/*
server/   BFF
  api/      маршруты под экраны
  graphql/  документы запросов и сгенерированные типы
  utils/    клиент GraphQL, приведение ошибок, кэш справочников
tests/    server/ — обработчики BFF, app/ — компоненты, e2e/ — сквозные сценарии
```

## Скиллы (`.agents/skills/`)

| Скилл | Когда |
|-------|-------|
| `nitro-bff` | любой маршрут в `server/`, граница «BFF — бэкенд» |
| `graphql-client-codegen` | запросы к бэкенду, типы из пакета `@keitaro-wrapper/contracts` |
| `design-tokens` | цвета, шрифты, отступы, темы |
| `editor-ui-states` | отображение потока и оффера: не опубликовано, removed, закрепление |
| `qa-e2e` | сквозные сценарии и проверка в браузере |
| `vue-best-practices`, `vue-testing-best-practices` | компоненты и их тесты |
| `design-system` | устройство токенов и спецификаций компонентов |

Установленные у разработчика глобально (в репозиторий не копируются): `nuxt`, `nitro`, `vue`, `vitest`, `vueuse-functions`, `impeccable` (критика и аудит интерфейса), `web-design-guidelines`, плагин `agent-skills`: `frontend-ui-engineering`.

## MCP

`.mcp.json`: `context7` — документация Nuxt, Nitro, Vue; `chrome-devtools` — снимки страницы, консоль, сеть, Lighthouse при проверке интерфейса.

## Правила части

- Компонент не знает о GraphQL и адресе бэкенда: только `useFetch`/`$fetch` к `/api/*`.
- BFF не считает доли и не решает, что можно, а что нельзя: это делает бэкенд.
- Цвета, шрифты и радиусы — только через токены из `DESIGN.md`; сырых значений в компонентах нет.
- Состояние не передаётся одним цветом (R-UX-11).
- Декоративной анимации нет; переходы отключаются при `prefers-reduced-motion`, заказанная смена состояния остаётся видимой без сдвига.
- Прокрутку не перехватывать.
