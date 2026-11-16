# Keitaro Wrapper — contracts

Контракт между бэкендом и фронтом. Единственное место правки — `schema.graphql`.

| Сборка | Пакет | Что внутри |
|--------|-------|------------|
| npm | `@keitaro-wrapper/contracts` | `schema.graphql`, типы TypeScript (`ts/generated.ts`) |
| Python | `keitaro-wrapper-contracts` | `schema.graphql`, типы Strawberry (`keitaro_contracts/types.py`) |

## Изменить контракт

```
$EDITOR schema.graphql          # типы, запросы, мутации
$EDITOR VERSION CHANGELOG.md    # semver: убрал или переименовал — мажор, добавил — минор
scripts/generate.sh             # типы Python и TypeScript, версия в package.json
scripts/check.sh                # линтеры, тесты, свежесть сгенерированного
```

Файлы `keitaro_contracts/types.py` и `ts/generated.ts` сгенерированы — руками не править.

## Собрать пакеты

```
uv build                        # dist/*.whl, dist/*.tar.gz
corepack pnpm pack              # *.tgz
```
