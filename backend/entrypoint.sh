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

# Wait for PostgreSQL using the already-installed psycopg2 driver.
info "Waiting for PostgreSQL..."
MAX_ATTEMPTS=60
ATTEMPT=1
while [ "$ATTEMPT" -le "$MAX_ATTEMPTS" ]; do
    if python -c 'import os, psycopg2; connection = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=3); connection.close()' >/dev/null 2>&1; then
        success "PostgreSQL is ready"
        break
    fi
    if [ "$ATTEMPT" -eq "$MAX_ATTEMPTS" ]; then
        error "PostgreSQL not ready after ${MAX_ATTEMPTS} attempts"
        exit 1
    fi
    info "  Attempt ${ATTEMPT}/${MAX_ATTEMPTS} - waiting..."
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
done

# Wait for Redis using redis-py instead of redis-tools.
info "Waiting for Redis..."
ATTEMPT=1
while [ "$ATTEMPT" -le "$MAX_ATTEMPTS" ]; do
    if python -c 'import os, redis; redis.Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=3, socket_timeout=3).ping()' >/dev/null 2>&1; then
        success "Redis is ready"
        break
    fi
    if [ "$ATTEMPT" -eq "$MAX_ATTEMPTS" ]; then
        error "Redis not ready after ${MAX_ATTEMPTS} attempts"
        exit 1
    fi
    info "  Attempt ${ATTEMPT}/${MAX_ATTEMPTS} - waiting..."
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
done

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
