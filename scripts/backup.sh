#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Environment-isolated backup
# Usage: ./scripts/backup.sh [output_dir] [production|staging]
#
# The selected environment determines the exact env file and Compose project.
# Secrets are passed to Compose via --env-file and are never sourced as shell.
###############################################################################

set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ERP_PROJECT_ROOT="${ERP_PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
ERP_DIR="${ERP_DIR:-/opt/erp-solution}"
COMPOSE_FILE="${ERP_COMPOSE_FILE:-${ERP_DIR}/docker-compose.prod.yml}"
OUTPUT_DIR="${1:-${ERP_DIR}/backups}"
ENVIRONMENT="${2:-production}"

case "${ENVIRONMENT}" in
    production|staging) ;;
    *)
        echo "Error: environment must be exactly 'production' or 'staging'." >&2
        exit 2
        ;;
esac

# Resolve only the environment-specific filename. Never accept an override or
# fall back to the other environment, even when the selected file is missing.
ENV_FILE="${ERP_DIR}/.env.${ENVIRONMENT}"
if [ -L "${ENV_FILE}" ]; then
    echo "Error: refusing a symlinked environment file: ${ENV_FILE}" >&2
    exit 1
fi
if [ ! -f "${ENV_FILE}" ]; then
    echo "Error: ${ENVIRONMENT} environment file not found: ${ENV_FILE}" >&2
    exit 1
fi
ENV_FILE_MODE="$(stat -c '%a' "${ENV_FILE}")" || {
    echo "Error: could not inspect environment file permissions." >&2
    exit 1
}
if (( (8#${ENV_FILE_MODE} & 077) != 0 )); then
    echo "Error: ${ENV_FILE} must not be accessible by group or other users (use chmod 600)." >&2
    exit 1
fi
if [ ! -f "${COMPOSE_FILE}" ]; then
    echo "Error: Compose file not found: ${COMPOSE_FILE}" >&2
    exit 1
fi
if [ ! -d "${ERP_PROJECT_ROOT}" ]; then
    echo "Error: repository source directory not found: ${ERP_PROJECT_ROOT}" >&2
    exit 1
fi

# Read simple KEY=VALUE settings without evaluating the env file as shell.
# Values are used only as single argv entries for pg_dump.
read_env_value() {
    local key="$1" file="$2"
    awk -v wanted="${key}" '
        /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
        {
            line=$0
            sub(/^[[:space:]]*/, "", line)
            split(line, pair, "=")
            if (pair[1] == wanted) {
                sub(/^[^=]*=/, "", line)
                sub(/[[:space:]]+#.*/, "", line)
                sub(/^[[:space:]]*/, "", line)
                sub(/[[:space:]]*$/, "", line)
                if (line ~ /^".*"$/ || line ~ /^\047.*\047$/) line=substr(line, 2, length(line)-2)
                value=line
            }
        }
        END { if (value != "") print value }
    ' "${file}"
}

DB_USER="$(read_env_value DB_USER "${ENV_FILE}")"
DB_NAME="$(read_env_value DB_NAME "${ENV_FILE}")"
DB_USER="${DB_USER:-erp}"
DB_NAME="${DB_NAME:-erp_solution}"

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker is required." >&2
    exit 1
fi
if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    echo "Error: neither 'docker compose' nor 'docker-compose' is available." >&2
    exit 1
fi

PROJECT_NAME="${ENVIRONMENT}-blue"
COMPOSE_ARGS=(--env-file "${ENV_FILE}" -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}")

# Fail before creating a backup that could be mistaken for a complete backup.
if ! "${COMPOSE[@]}" "${COMPOSE_ARGS[@]}" exec -T postgres pg_isready -U "${DB_USER}" -d "${DB_NAME}" >/dev/null 2>&1; then
    echo "Error: ${ENVIRONMENT} PostgreSQL is not ready; no backup was created." >&2
    exit 1
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_NAME="erp_backup_${ENVIRONMENT}_${TIMESTAMP}"
BACKUP_PATH="${OUTPUT_DIR%/}/${BACKUP_NAME}"
mkdir -p "${OUTPUT_DIR}"
if [ -e "${BACKUP_PATH}" ]; then
    echo "Error: backup destination already exists: ${BACKUP_PATH}" >&2
    exit 1
fi
mkdir -m 0700 "${BACKUP_PATH}"

cleanup() {
    local status=$?
    if [ "$status" -ne 0 ]; then
        rm -rf -- "${BACKUP_PATH}"
        echo "Backup failed; incomplete output removed." >&2
    fi
    exit "$status"
}
trap cleanup EXIT

echo "Backing up ${ENVIRONMENT} into ${BACKUP_PATH}"

tar -czf "${BACKUP_PATH}/source_code.tar.gz" \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='.env.*' \
    --exclude='backups' \
    -C "${ERP_PROJECT_ROOT}" .

"${COMPOSE[@]}" "${COMPOSE_ARGS[@]}" exec -T postgres \
    pg_dump --no-owner --no-acl -U "${DB_USER}" "${DB_NAME}" \
    > "${BACKUP_PATH}/database.sql"

if [ ! -s "${BACKUP_PATH}/database.sql" ]; then
    echo "Error: PostgreSQL returned an empty dump." >&2
    exit 1
fi

cat > "${BACKUP_PATH}/manifest.txt" <<EOF
ERP SOLUTION Backup
===================
Created: $(date -Is)
Environment: ${ENVIRONMENT}
Compose project: ${PROJECT_NAME}
Database: ${DB_NAME}
Database user: ${DB_USER}
Source revision: $(git -C "${ERP_PROJECT_ROOT}" rev-parse HEAD 2>/dev/null || echo unknown)

Contents:
- source_code.tar.gz (repository source; env files and secrets excluded)
- database.sql (PostgreSQL plain SQL dump)
- manifest.txt (backup metadata)

Runtime environment files are deliberately not copied. Restore configuration
from the approved secret manager; never copy production secrets into staging.
EOF

trap - EXIT
echo "Backup complete: ${BACKUP_PATH}"
