#!/usr/bin/env bash
# Run the backend with Jev-Intercept enabled.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

cd "$REPO_ROOT/backend"
. venv/bin/activate

export JEV_INTERCEPT=1
export JEV_INTERCEPT_MODULES="${JEV_INTERCEPT_MODULES:-app.routers,app.services,app.models}"

exec uvicorn app.main:app --reload "$@"
