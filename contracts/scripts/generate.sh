#!/usr/bin/env bash
# Regenerate Python and TypeScript types from schema.graphql and sync the version.
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --quiet
uv run python scripts/generate.py
corepack pnpm install --silent
corepack pnpm --silent codegen
echo "generated ts/generated.ts"
