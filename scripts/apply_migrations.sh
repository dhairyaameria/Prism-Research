#!/usr/bin/env bash
# Apply SQL migrations to an *existing* Postgres (Docker volume keeps old schema until you migrate).
# Fresh `docker compose up` only runs init.sql on first create; code/ORM can move ahead of your DB.
#
# Usage (from repo root, with prism/.env):
#   ./scripts/apply_migrations.sh
#
# Requires: psql (brew install libpq) and DATABASE_URL in the environment or in ./.env
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

URL="${DATABASE_URL:-postgresql+asyncpg://prism:prism@127.0.0.1:5433/prism}"
# psql does not accept SQLAlchemy's +asyncpg driver suffix
PSQL_URL="${URL//+asyncpg/}"

if ! command -v psql >/dev/null 2>&1; then
  echo "error: psql not found (e.g. brew install libpq && brew link --force libpq)" >&2
  exit 1
fi

for f in \
  "${ROOT}/scripts/migrations/001_tenant_llm.sql" \
  "${ROOT}/scripts/migrations/002_architecture_plane.sql" \
  "${ROOT}/scripts/migrations/003_evidence_access_subject.sql" \
  "${ROOT}/scripts/migrations/004_rename_demo_tickers_to_company.sql"
do
  echo "==> $f"
  psql "$PSQL_URL" -v ON_ERROR_STOP=1 -f "$f"
done
echo "==> migrations applied OK"
