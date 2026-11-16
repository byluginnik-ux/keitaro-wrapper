#!/usr/bin/env bash
# The gate for the contract: generated files are fresh, linters and tests pass (R-ARCH-09).
set -euo pipefail
cd "$(dirname "$0")/.."

GENERATED=(keitaro_contracts/types.py ts/generated.ts package.json)

scripts/generate.sh
if ! git diff --quiet -- "${GENERATED[@]}"; then
  echo "contracts: generated files are stale — commit the result of scripts/generate.sh" >&2
  git --no-pager diff --stat -- "${GENERATED[@]}" >&2
  exit 1
fi
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
