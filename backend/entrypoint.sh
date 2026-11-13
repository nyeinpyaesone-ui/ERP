#!/bin/bash
###############################################################################
# ERP SOLUTION — Backend Entrypoint
# Handles migrations, validation, and startup
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    local level="$1"
    shift
    local msg="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${msg}"
}

info() { log "INFO" "${BLUE}$*${NC}"; }
success() { log "SUCCESS" "${GREEN}$*${NC}"; }
warn() { log "WARN" "${YELLOW}$*${NC}"; }
error() { log "ERROR" "${RED}$*${NC}"; }

# Required environment variables
REQUIRED_VARS=(
    "DATABASE_URL"
    "REDIS_URL"
    "SECRET_KEY"
    "ENVIRONMENT"
)

# Optional but recommended
OPTIONAL_VARS=(
    "OLLAMA_BASE_URL"
    "STRIPE_SECRET_KEY"
    "CORS_ORIGINS"
)

info "=========================================="
info "ERP SOLUTION — Backend Starting"
info "Environment: ${ENVIRONMENT:-unknown}"
info "=========================================="

# Validate required environment variables
info "Validating environment variables..."
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        error "Required environment variable not set: ${var}"
        exit 1
    else
        info "  ${var} = SET"
    fi
done

for var in "${OPTIONAL_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        warn "  ${var} = NOT SET (optional)"
    else
        info "  ${var} = SET"
    fi
done

success "Environment validation passed"

# Wait for PostgreSQL and Redis using the production Python drivers.
# This avoids shipping postgresql-client and redis-tools in the runtime image.
info "Waiting for PostgreSQL and Redis..."
python - <<'PY'
import os
import sys
import time

import redis
from sqlalchemy import create_engine, text

engine = create_engine(
    os.environ["DATABASE_URL"],
    connect_args={"connect_timeout": 2},
)
redis_client = redis.Redis.from_url(
    os.environ["REDIS_URL"],
    socket_connect_timeout=2,
    socket_timeout=2,
)

def wait_for(label, probe):
    max_attempts = 60
    for attempt in range(1, max_attempts + 1):
        try:
            probe()
            print(f"[SUCCESS] {label} is ready", flush=True)
            return
        except Exception as exc:
            if attempt == max_attempts:
                print(
                    f"[ERROR] {label} not ready after {max_attempts} attempts "
                    f"({type(exc).__name__})",
                    file=sys.stderr,
                    flush=True,
                )
                raise SystemExit(1) from exc
            print(
                f"[INFO] {label} readiness attempt {attempt}/{max_attempts} "
                f"({type(exc).__name__}); retrying",
                flush=True,
            )
            time.sleep(1)

def check_postgres():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

try:
    wait_for("PostgreSQL", check_postgres)
    wait_for("Redis", redis_client.ping)
finally:
    engine.dispose()
    redis_client.close()
PY

# Run database migrations
info "Running database migrations..."
if alembic upgrade head; then
    success "Migrations completed"
else
    error "Migration failed"
    exit 1
fi

# Seed default data (roles, permissions, etc.)
info "Seeding default data..."
if python -m app.scripts.seed_defaults; then
    success "Default data seeded"
else
    error "Seed script failed"
    exit 1
fi

# Create uploads directory
mkdir -p /app/uploads /app/static

success "=========================================="
success "Backend initialization complete"
success "Starting application..."
success "=========================================="

# Execute the main command
exec "$@"
