#!/usr/bin/env bash
# Run Prism API from repo root (correct PYTHONPATH + Python 3.11).
# Usage:
#   ./scripts/run-api.sh --reload
#   nohup ./scripts/run-api.sh --reload > /tmp/prism-api.log 2>&1 &
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/apps/api/src:${ROOT}"

if command -v python3.11 >/dev/null 2>&1; then
  PY=(python3.11)
elif [[ -x /opt/homebrew/bin/python3.11 ]]; then
  PY=(/opt/homebrew/bin/python3.11)
else
  echo "error: need python3.11 (Homebrew: brew install python@3.11)" >&2
  exit 1
fi

exec "${PY[@]}" -m uvicorn prism_api.main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}" "$@"
