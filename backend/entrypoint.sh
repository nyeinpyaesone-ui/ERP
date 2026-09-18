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

# Wait for PostgreSQL
info "Waiting for PostgreSQL..."
DB_HOST=$(echo "${DATABASE_URL}" | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo "${DATABASE_URL}" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')

if [ -z "${DB_HOST}" ] || [ -z "${DB_PORT}" ]; then
    error "Could not parse DATABASE_URL: ${DATABASE_URL}"
    exit 1
fi

info "  Host: ${DB_HOST}, Port: ${DB_PORT}"

MAX_ATTEMPTS=60
ATTEMPT=1
while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    if pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -q 2>/dev/null; then
        success "PostgreSQL is ready"
        break
    fi
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        error "PostgreSQL not ready after ${MAX_ATTEMPTS} attempts"
        exit 1
    fi
    info "  Attempt ${ATTEMPT}/${MAX_ATTEMPTS} - waiting..."
    sleep 2
    ((ATTEMPT++))
done

# Wait for Redis
info "Waiting for Redis..."
REDIS_HOST=$(echo "${REDIS_URL}" | sed -n 's/.*@\([^:]*\):.*/\1/p')
REDIS_PORT=$(echo "${REDIS_URL}" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')

if [ -z "${REDIS_HOST}" ] || [ -z "${REDIS_PORT}" ]; then
    # Try alternative format redis://:password@host:port/db
    REDIS_HOST=$(echo "${REDIS_URL}" | sed -n 's/.*@\([^:]*\):.*/\1/p')
    REDIS_PORT=$(echo "${REDIS_URL}" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
fi

if [ -z "${REDIS_HOST}" ] || [ -z "${REDIS_PORT}" ]; then
    warn "Could not parse REDIS_URL, using defaults"
    REDIS_HOST="redis"
    REDIS_PORT="6379"
fi

info "  Host: ${REDIS_HOST}, Port: ${REDIS_PORT}"

ATTEMPT=1
while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    if redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping 2>/dev/null | grep -q PONG; then
        success "Redis is ready"
        break
    fi
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        error "Redis not ready after ${MAX_ATTEMPTS} attempts"
        exit 1
    fi
    info "  Attempt ${ATTEMPT}/${MAX_ATTEMPTS} - waiting..."
    sleep 2
    ((ATTEMPT++))
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
if python -m app.scripts.seed_defaults 2>/dev/null; then
    success "Default data seeded"
else
    warn "Seed script not found or failed (continuing anyway)"
fi

# Create uploads directory
mkdir -p /app/uploads /app/static

success "=========================================="
success "Backend initialization complete"
success "Starting application..."
success "=========================================="

# Execute the main command
exec "$@"