#!/usr/bin/env bash
# Run deliberately by the owner. No indexing or live provider calls.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
result=0
uv sync --locked || exit 1
uvx --from ruff==0.15.8 ruff check . || result=1
uvx --with pydantic --from mypy==1.18.2 mypy lib/measurements.py lib/prompt_contract.py --follow-imports=silent || result=1
uv run pytest -q || result=1
uv run python scripts/check_doc_claims.py || result=1
git diff --check || result=1
exit "$result"
