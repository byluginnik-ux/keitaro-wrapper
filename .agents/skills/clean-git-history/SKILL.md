---
name: clean-git-history
description: Правила коммитов, веток и слияния в этом репозитории. Использовать перед каждым git commit, созданием ветки, rebase и слиянием в main, а также когда нужно исправить уже сделанный коммит. Не даёт разрешения на push — его даёт только человек.
---

# Чистая история

История читается проверяющим как рассказ о ходе работы: тест → реализация → следующая фича.

## Сообщение

```
<тип>(<часть>/<область>): <что сделано, повелительное наклонение, до 72 знаков>

<зачем — если не очевидно из заголовка>
```

Типы: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`, `ci`, `style`, `perf`.
Часть: `backend`, `frontend` или без неё для общего. Примеры областей: `keitaro`, `graphql`, `storage`, `creator`, `editor`, `shares`, `bff`, `ui`.
Язык сообщений — английский.

```
test(backend/shares): cover pinned share redistribution
feat(backend/shares): keep pinned shares on recalculation
docs(spec): forbid publishing a stream without active offers
```

## Один коммит — одна мысль

- Не смешивать части: правка в `backend/` и `frontend/` — два коммита.
- Не смешивать тест и реализацию, рефакторинг и изменение поведения, форматирование и логику.
- Не коммитить «wip», «fix typo», «review fixes». Незапушенную ошибку править `git commit --amend` или `git commit --fixup <sha>` + `git rebase --autosquash`.
- В индекс добавлять файлы поимённо (`git add <путь>`), а не `git add -A`: так в коммит не попадёт случайное.

## Ветки

- `main` всегда зелёный. Работа — в `feat/Fxx-краткое-имя` (номер из `docs/FEATURES.md`).
- Перед слиянием: `git rebase main`, затем `git switch main && git merge --ff-only feat/Fxx-…`. Merge-коммитов нет.
- Ветка после слияния удаляется.

## Перед коммитом

1. `git status` и `git diff --staged` — в индексе только задуманное.
2. Хуки pre-commit проходят (ruff, pyright, eslint, gitleaks, формат сообщения). Хук не обходить флагом `--no-verify`.
3. Секретов нет: `.env` не в индексе.

## После публикации

Опубликованную историю не переписывать. `git push --force` — только по прямому указанию человека.
