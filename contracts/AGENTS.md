# Contracts — правила для агентов

Контракт между `backend/` и `frontend/`: схема GraphQL и сгенерированные из неё типы. Публикуемая единица: npm-пакет `@keitaro-wrapper/contracts` и пакет Python `keitaro-wrapper-contracts`. Общие правила — в `../AGENTS.md`.

## Команды

```
scripts/generate.sh     # типы Python и TypeScript из schema.graphql, версия в package.json
scripts/check.sh        # свежесть сгенерированного, ruff, pyright, тесты пакета
uv build                # wheel и sdist
corepack pnpm pack      # архив npm
```

## Правила

- Руками правятся только `schema.graphql`, `VERSION`, `CHANGELOG.md`.
- `keitaro_contracts/types.py`, `ts/generated.ts` и версия в `package.json` — сгенерированы. Правка руками запрещена; `scripts/check.sh` её обнаружит.
- Любое изменение схемы — новая версия и запись в `CHANGELOG.md` в том же коммите.
- `Query` и `Mutation` в схеме описывают сигнатуры; их резолверы пишет бэкенд, поэтому в `types.py` корневых операций нет.
- Изменение контракта идёт первым коммитом (`feat(contracts): …`), затем отдельные коммиты бэкенда и фронта.
- Публикация пакетов в реестры — только по прямому указанию человека.

Порядок изменения — скилл `contract-change`.
