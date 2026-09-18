#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Backup Script
# Usage: ./scripts/backup.sh [output_dir] [environment]
#   environment: production (default) | staging
###############################################################################

set -e

OUTPUT_DIR="${1:-/opt/erp-solution/backups}"
ENVIRONMENT="${2:-production}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="erp_backup_${ENVIRONMENT}_${TIMESTAMP}"
BACKUP_PATH="${OUTPUT_DIR}/${BACKUP_NAME}"

DOCKER_COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
fi

PROJECT_NAME="${ENVIRONMENT}-blue"
COMPOSE_FILE="/opt/erp-solution/docker-compose.prod.yml"
ENV_FILE="/opt/erp-solution/.env.production"

if [ -f "${ENV_FILE}" ]; then
    set -a
    source "${ENV_FILE}"
    set +a
fi

echo "=========================================="
echo "  ERP SOLUTION Backup (${ENVIRONMENT})"
echo "=========================================="
echo "  Destination: ${BACKUP_PATH}"
echo ""

mkdir -p "${BACKUP_PATH}"

# Backup source code (excluding .git and node_modules)
echo "[1/4] Backing up source code..."
tar -czf "${BACKUP_PATH}/source_code.tar.gz"     --exclude='.git'     --exclude='node_modules'     --exclude='venv'     --exclude='__pycache__'     --exclude='*.pyc'     /opt/erp-solution 2>/dev/null || tar -czf "${BACKUP_PATH}/source_code.tar.gz" --exclude='.git' --exclude='node_modules' --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' .
echo "  ✓ Source code backed up"

# Backup database (if running)
echo "[2/4] Backing up database..."
if ${DOCKER_COMPOSE_CMD} -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" ps postgres 2>/dev/null | grep -q "Up"; then
    ${DOCKER_COMPOSE_CMD} -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" exec -T postgres pg_dump -U erp erp_solution > "${BACKUP_PATH}/database.sql"
    echo "  ✓ Database backed up"
else
    echo "  ! PostgreSQL not running, skipping database backup"
fi

# Backup environment files
echo "[3/4] Backing up environment files..."
if [ -f "${ENV_FILE}" ]; then
    cp "${ENV_FILE}" "${BACKUP_PATH}/env.production"
fi
echo "  ✓ Environment files backed up"

# Create backup manifest
echo "[4/4] Creating backup manifest..."
cat > "${BACKUP_PATH}/manifest.txt" << EOF
ERP SOLUTION Backup
======================
Date: $(date)
Environment: ${ENVIRONMENT}
Version: $(git describe --tags --always 2>/dev/null || echo "unknown")
Commit: $(git rev-parse HEAD 2>/dev/null || echo "unknown")
Branch: $(git branch --show-current 2>/dev/null || echo "unknown")

Contents:
- source_code.tar.gz (full source)
- database.sql (PostgreSQL dump)
- env.production (production configuration)
EOF
echo "  ✓ Manifest created"

echo ""
echo "=========================================="
echo "  Backup Complete!"
echo "  Location: ${BACKUP_PATH}"
echo "=========================================="
