#!/usr/bin/env bash
# Regression tests for environment isolation in scripts/backup.sh.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

mkdir -p "${TMP}/bin" "${TMP}/runtime" "${TMP}/repo"
touch "${TMP}/runtime/docker-compose.prod.yml"
cat > "${TMP}/runtime/.env.production" <<'EOF'
DB_USER=prod_user
DB_NAME=prod_database
DB_PASSWORD=prod-secret
EOF
cat > "${TMP}/runtime/.env.staging" <<'EOF'
DB_USER=stage_user
DB_NAME=stage_database
DB_PASSWORD=stage-secret
EOF

cat > "${TMP}/bin/docker" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "${DOCKER_CALL_LOG}"
if [[ "$*" == "compose version" ]]; then exit 0; fi
if [[ "$*" == *"pg_isready"* ]]; then
    [[ "$*" == *".env.staging"* && "$*" == *"stage_user"* && "$*" == *"stage_database"* ]] || {
        echo "staging preflight did not use staging settings" >&2; exit 91;
    }
    [[ "$*" != *"prod-secret"* ]] || exit 92
    exit 0
fi
if [[ "$*" == *"pg_dump"* ]]; then
    [[ "$*" == *".env.staging"* && "$*" == *"stage_user"* && "$*" == *"stage_database"* ]] || {
        echo "staging dump did not use staging settings" >&2; exit 93;
    }
    printf '%s\n' "-- staging database dump"
    exit 0
fi
exit 0
MOCK
chmod +x "${TMP}/bin/docker"

export PATH="${TMP}/bin:${PATH}"
export DOCKER_CALL_LOG="${TMP}/docker.log"
export ERP_DIR="${TMP}/runtime"
export ERP_PROJECT_ROOT="${TMP}/repo"
export ERP_COMPOSE_FILE="${TMP}/runtime/docker-compose.prod.yml"

# Staging must use its own env file, Compose project and database settings.
"${ROOT}/scripts/backup.sh" "${TMP}/out" staging
grep -q -- '--env-file ${TMP}/runtime/.env.staging' "${DOCKER_CALL_LOG}"
grep -q -- '-p staging-blue' "${DOCKER_CALL_LOG}"
grep -q -- 'pg_dump.*stage_user.*stage_database' "${DOCKER_CALL_LOG}"
! grep -q 'prod-secret' "${DOCKER_CALL_LOG}"
test -s "${TMP}/out"/erp_backup_staging_*/database.sql

# Missing staging config must fail closed and must not fall back to production.
mv "${TMP}/runtime/.env.staging" "${TMP}/runtime/.env.staging.off"
if "${ROOT}/scripts/backup.sh" "${TMP}/missing-out" staging >/dev/null 2>&1; then
    echo "expected missing staging env file to fail" >&2
    exit 1
fi
test ! -e "${TMP}/missing-out"

# Unsupported environment names must fail before any output is created.
if "${ROOT}/scripts/backup.sh" "${TMP}/invalid-out" preview >/dev/null 2>&1; then
    echo "expected unsupported environment to fail" >&2
    exit 1
fi
test ! -e "${TMP}/invalid-out"

echo "Backup environment-isolation tests passed."
