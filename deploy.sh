#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Push the current tree to a server and deploy it
#
# Usage:
#   ./deploy.sh user@host                       # first install on the host
#   ./deploy.sh root@1.2.3.4 --version=v1.1.1
#   ./deploy.sh root@1.2.3.4 --mode=blue-green --version=v1.1.1
#
# Flags:
#   --version=TAG     Image tag to deploy (default: VERSION, then latest git tag)
#   --mode=MODE       bootstrap (default) | blue-green | push-only
#   --dir=PATH        Remote install directory (default: /opt/erp-solution)
#   --ssh-key=FILE    Identity file (default: ssh config / agent)
#   --port=N          SSH port (default: 22)
#   --no-sync         Skip rsync, deploy whatever is already on the host
#   --skip-deps       Do not install packages on the remote
#   --dry-run         Print the remote commands, execute nothing
#
# Modes:
#   bootstrap   First install: prepare the host, generate .env.production,
#               pull or build images, migrate, start, wait for health
#   blue-green  An existing install: hand off to scripts/deploy-blue-green.sh
#   push-only   Sync the tree and nothing else
#
# Secrets are never transferred. The remote env file is generated on the remote
# host if absent and left untouched if present.
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
. "${SCRIPT_DIR}/scripts/lib.sh"

TARGET=""
VERSION_ARG=""
MODE="bootstrap"
REMOTE_DIR="/opt/erp-solution"
SSH_PORT=22
SSH_KEY=""
NO_SYNC=false
SKIP_DEPS=false
DRY_RUN=false

for arg in "$@"; do
    case "${arg}" in
        --version=*)  VERSION_ARG="${arg#*=}" ;;
        --mode=*)     MODE="${arg#*=}" ;;
        --dir=*)      REMOTE_DIR="${arg#*=}" ;;
        --ssh-key=*)  SSH_KEY="${arg#*=}" ;;
        --port=*)     SSH_PORT="${arg#*=}" ;;
        --no-sync)    NO_SYNC=true ;;
        --skip-deps)  SKIP_DEPS=true ;;
        --dry-run)    DRY_RUN=true ;;
        --help|-h)    erp_help "${BASH_SOURCE[0]}"; exit 0 ;;
        -*)           erp_die "Unknown option: ${arg} (try --help)" ;;
        *)            TARGET="${arg}" ;;
    esac
done

VERSION="$(erp_detect_version "${VERSION_ARG}")"
DOCKER_USER_ARG="$(erp_detect_docker_user)"

# Reject anything that would be re-interpreted by a shell on either side. These
# values are interpolated into remote commands and into image references.
validate() {
    [ -n "${TARGET}" ] || { erp_help "${BASH_SOURCE[0]}"; erp_die "A target host is required."; }
    case "${MODE}" in
        bootstrap|blue-green|push-only) ;;
        *) erp_die "Unknown --mode: ${MODE} (bootstrap|blue-green|push-only)" ;;
    esac
    case "${VERSION}" in
        ''|*[!A-Za-z0-9._-]*) erp_die "Unsafe VERSION: '${VERSION}'" ;;
    esac
    case "${DOCKER_USER_ARG}" in
        ''|*[!A-Za-z0-9._-]*) erp_die "Unsafe DOCKER_USER: '${DOCKER_USER_ARG}'" ;;
    esac
    case "${REMOTE_DIR}" in
        /*) ;;
        *) erp_die "--dir must be an absolute path: ${REMOTE_DIR}" ;;
    esac
    case "${REMOTE_DIR}" in
        *"'"*|*'$'*|*'`'*|*' '*|*';'*|*'&'*|*'|'*|*'>'*|*'<'*)
            erp_die "--dir contains unsafe shell characters: ${REMOTE_DIR}" ;;
    esac
    # The target becomes both an ssh argument and part of the rsync remote
    # spec, so keep it to the shapes those accept.
    case "${TARGET}" in
        *"'"*|*'$'*|*'`'*|*' '*|*';'*|*'&'*|*'|'*|*'>'*|*'<'*|*'\\'*)
            erp_die "Target host contains unsafe characters: ${TARGET}" ;;
    esac
    case "${TARGET}" in
        *@*) TARGET_HOST="${TARGET#*@}" ;;
        *)   TARGET_HOST="${TARGET}" ;;
    esac
    # Strip a :port suffix, but only for the unbracketed form. A bracketed IPv6
    # literal is full of colons and must not be truncated at the first one.
    case "${TARGET_HOST}" in
        \[*\]) : ;;
        *:*)    TARGET_HOST="${TARGET_HOST%%:*}" ;;
    esac
    # Hostname, IPv4, or a bracketed IPv6 literal as ssh and rsync accept it.
    case "${TARGET_HOST}" in
        \[*\])
            printf '%s' "${TARGET_HOST}" | grep -Eq '^\[[0-9A-Fa-f:.]+\]$' \
                || erp_die "Not a valid IPv6 address: ${TARGET_HOST}" ;;
        *) printf '%s' "${TARGET_HOST}" | grep -Eq '^[A-Za-z0-9._-]+$' \
            || erp_die "Not a valid host name or IP: ${TARGET_HOST}" ;;
    esac
}

SSH_OPTS=(-p "${SSH_PORT}" -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=30)
[ -n "${SSH_KEY}" ] && SSH_OPTS+=(-i "${SSH_KEY}")

# Read a script body on stdin and run it over SSH. The body is written with a
# quoted heredoc in the caller, so nothing inside it is expanded locally, and
# the handful of values it does need arrive as environment variables instead of
# being spliced into the source.
run_remote() {
    if [ "${DRY_RUN}" = true ]; then
        return 0
    fi
    ssh "${SSH_OPTS[@]}" "${TARGET}" \
        "ERP_DIR='${REMOTE_DIR}' ERP_USER_ARG='${DOCKER_USER_ARG}' ERP_VERSION='${VERSION}' ERP_SKIP_DEPS='${SKIP_DEPS}' bash -s"
}

show_remote() {
    erp_info "[dry-run] would run this on ${TARGET}:"
    sed 's/^/    /'
}

preflight_local() {
    erp_require_cmd ssh
    if [ "${NO_SYNC}" = false ]; then
        erp_require_cmd rsync
        [ -f "${ERP_PROJECT_ROOT}/docker-compose.prod.yml" ] \
            || erp_die "docker-compose.prod.yml not found in ${ERP_PROJECT_ROOT}"
        if [ -f "${ERP_PROJECT_ROOT}/.env.production" ]; then
            erp_warn ".env.production exists locally and will NOT be transferred;"
            erp_warn "the remote generates or reuses its own copy."
        fi
    fi
}

preflight_remote() {
    local out
    out="$(printf 'echo ERP_REACHABLE\n' | run_remote 2>/dev/null || true)"
    case "${out}" in
        *ERP_REACHABLE*) return 0 ;;
        *) erp_die "Cannot reach ${TARGET} over SSH (port ${SSH_PORT})." ;;
    esac
}

sync_tree() {
    if [ "${NO_SYNC}" = true ]; then
        erp_info "Skipping sync (--no-sync)"
        return 0
    fi
    erp_step "Syncing repository to ${TARGET}:${REMOTE_DIR}"
    # Exclude what the remote rebuilds anyway (venv, node_modules) and what must
    # never leave this workstation (env files, VCS history, local state).
    local excludes=(
        --exclude='.git'
        --exclude='node_modules'
        --exclude='venv'
        --exclude='.venv'
        --exclude='__pycache__'
        --exclude='*.pyc'
        --exclude='*.heapsnapshot'
        --exclude='dist'
        --exclude='build'
        --exclude='.pytest_cache'
        --exclude='.ruff_cache'
        --exclude='.mypy_cache'
        --exclude='htmlcov'
        --exclude='.coverage'
        --exclude='coverage.xml'
        --exclude='.env'
        --exclude='.env.*'
        --exclude='*.db'
        --exclude='*.sqlite'
        --exclude='backups'
        --exclude='logs'
        --exclude='ssl'
        --exclude='session-*.md'
    )
    if [ "${DRY_RUN}" = true ]; then
        erp_info "[dry-run] rsync -az --delete ${excludes[*]} ./ ${TARGET}:${REMOTE_DIR}/"
        return 0
    fi
    rsync -az --delete --delay-updates "${excludes[@]}" \
        -e "ssh -p ${SSH_PORT}${SSH_KEY:+ -i ${SSH_KEY}}" \
        "${ERP_PROJECT_ROOT}/" "${TARGET}:${REMOTE_DIR}/"
    erp_success "Tree synced"
}

###############################################################################
# bootstrap: first install on a clean host
###############################################################################

remote_bootstrap() {
    erp_step "Bootstrapping ${REMOTE_DIR} on ${TARGET}"

    cat <<'REMOTE_BOOTSTRAP' | { [ "${DRY_RUN}" = true ] && show_remote || run_remote; }
set -euo pipefail
cd "${ERP_DIR}"

# --- preconfigure the host --------------------------------------------------
# Prefer the version of lib.sh that was just synced: the remote then gets the
# same package list, daemon start logic and port/disk checks as a local run.
LIB="scripts/lib.sh"
if [ "${ERP_SKIP_DEPS}" != "true" ] && [ -f "${LIB}" ]; then
    # shellcheck source=scripts/lib.sh
    . "./${LIB}"
    erp_preconfigure
    DC=("${ERP_COMPOSE_CMD}")
else
    echo '--- prerequisites (minimal path) ---'
    if command -v apt-get >/dev/null; then
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y -qq curl ca-certificates openssl \
            || { echo 'ERROR: cannot install curl/ca-certificates/openssl' >&2; exit 1; }
        apt-get install -y -qq gnupg rsync certbot 2>/dev/null \
            || echo 'note: certbot/rsync unavailable; TLS and rsync deploys disabled'
    fi
    if ! command -v docker >/dev/null; then
        curl -fsSL https://get.docker.com | sh
        systemctl enable --now docker || true
    fi
    docker info >/dev/null 2>&1 || { systemctl start docker || true; }
    if docker compose version >/dev/null 2>&1; then
        DC=(docker compose)
    elif command -v docker-compose >/dev/null; then
        DC=(docker-compose)
    else
        apt-get install -y -qq docker-compose-plugin 2>/dev/null || true
        if docker compose version >/dev/null 2>&1; then
            DC=(docker compose)
        else
            curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
                -o /usr/local/bin/docker-compose
            chmod +x /usr/local/bin/docker-compose
            DC=(docker-compose)
        fi
    fi
fi
docker info >/dev/null 2>&1 || {
    echo 'ERROR: the Docker daemon is not answering after provisioning.' >&2
    echo '       start it (systemctl start docker) and re-run.' >&2
    exit 1
}
echo "compose: ${DC[*]}"

# --- directories the compose file bind-mounts --------------------------------
mkdir -p ssl logs/nginx backups backend/uploads
chmod 700 ssl

# --- environment ------------------------------------------------------------
ENV_FILE="${ERP_DIR}/.env.production"
if [ -f "${ENV_FILE}" ]; then
    echo "reusing ${ENV_FILE}"
else
    echo '--- generating .env.production ---'
    umask 077
    {
        echo "# Generated by deploy.sh on $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
        echo "DB_USER=erp"
        printf 'DB_PASSWORD=%s\n' "$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | cut -c1-48)"
        echo "DB_NAME=erp_solution"
        printf 'REDIS_PASSWORD=%s\n' "$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | cut -c1-48)"
        printf 'SECRET_KEY=%s\n' "$(openssl rand -hex 32)"
        echo "ALGORITHM=HS256"
        echo "ACCESS_TOKEN_EXPIRE_MINUTES=30"
        echo "REFRESH_TOKEN_EXPIRE_DAYS=7"
        # Settings uses a Literal; 'production' raises at import and the
        # container will not boot.
        echo "ENVIRONMENT=prod"
        echo "OLLAMA_BASE_URL=http://ollama:11434"
        echo "OLLAMA_MODEL=llama3.1"
        echo "DOCKER_USER=${ERP_USER_ARG}"
        echo "VERSION=${ERP_VERSION}"
        echo "UPLOAD_DIR=/app/uploads"
        echo "MAX_UPLOAD_SIZE=52428800"
        echo "WS_HEARTBEAT_INTERVAL=30"
        echo "CORS_ORIGINS=https://app.example.com"
        echo "# Replace CORS_ORIGINS with your real app origin before serving traffic."
    } > "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
fi

# --- validate before starting anything --------------------------------------
echo '--- validating compose ---'
"${DC[@]}" --env-file "${ENV_FILE}" -f docker-compose.prod.yml config >/dev/null

# --- images -----------------------------------------------------------------
echo '--- images ---'
if ! "${DC[@]}" --env-file "${ENV_FILE}" -f docker-compose.prod.yml pull backend frontend; then
    echo 'registry pull failed; building on this host instead'
    V="$(sed -n 's/^VERSION=//p' "${ENV_FILE}" | tail -n1)"
    V="${V:-${ERP_VERSION}}"
    U="$(sed -n 's/^DOCKER_USER=//p' "${ENV_FILE}" | tail -n1)"
    U="${U:-${ERP_USER_ARG}}"
    docker build -t "${U}/erp-solution-backend:${V}" ./backend
    docker build -t "${U}/erp-solution-frontend:${V}" ./backend/frontend-react
fi

# --- start ------------------------------------------------------------------
echo '--- starting stack ---'
"${DC[@]}" --env-file "${ENV_FILE}" -f docker-compose.prod.yml up -d postgres redis ollama
"${DC[@]}" --env-file "${ENV_FILE}" -f docker-compose.prod.yml up -d nginx frontend backend

# entrypoint.sh waits for Postgres and Redis, then runs Alembic, so the backend
# healthcheck can take a minute on a cold volume.
echo '--- waiting for backend health ---'
for _ in $(seq 1 60); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
        erp-blue-backend 2>/dev/null || echo missing)"
    case "${status}" in
        healthy) echo 'backend healthy'; break ;;
        unhealthy)
            echo 'backend unhealthy; last 60 log lines:' >&2
            docker logs erp-blue-backend --tail 60 >&2
            exit 1
            ;;
    esac
    sleep 5
done
if [ "${status}" != "healthy" ]; then
    echo "ERROR: backend never became healthy (last status: ${status})" >&2
    docker logs erp-blue-backend --tail 60 >&2 || true
    exit 1
fi

"${DC[@]}" --env-file "${ENV_FILE}" -f docker-compose.prod.yml ps
REMOTE_BOOTSTRAP

    [ "${DRY_RUN}" = true ] || erp_success "Remote bootstrap finished"
}

###############################################################################
# blue-green: hand off to the in-tree deployer
###############################################################################

remote_blue_green() {
    erp_step "Handing off to the blue-green deployer on ${TARGET}"
    cat <<'REMOTE_BLUE_GREEN' | { [ "${DRY_RUN}" = true ] && show_remote || run_remote; }
set -euo pipefail
cd "${ERP_DIR}"
[ -f .env.production ] || {
    echo "no .env.production in ${ERP_DIR}; run --mode=bootstrap first" >&2
    exit 1
}
[ -x scripts/deploy-blue-green.sh ] || chmod +x scripts/deploy-blue-green.sh
VERSION="${ERP_VERSION}" ./scripts/deploy-blue-green.sh production "${ERP_VERSION}"
REMOTE_BLUE_GREEN

    [ "${DRY_RUN}" = true ] || erp_success "Blue-green deploy finished"
}

###############################################################################

print_summary() {
    local ssh_cmd="ssh -p ${SSH_PORT}${SSH_KEY:+ -i ${SSH_KEY}} ${TARGET}"
    cat <<EOF

==========================================
  ERP SOLUTION — deploy complete
==========================================

  Target:   ${TARGET}:${REMOTE_DIR}
  Version:  ${VERSION}
  Images:   ${DOCKER_USER_ARG}/erp-solution-backend:${VERSION}
            ${DOCKER_USER_ARG}/erp-solution-frontend:${VERSION}

  Follow up:
    ${ssh_cmd}
    cd ${REMOTE_DIR}
    docker compose -f docker-compose.prod.yml --env-file .env.production ps
    docker logs erp-blue-backend -f

  Before serving real traffic:
    1. Set CORS_ORIGINS in .env.production to your real app origin.
    2. Point app.<domain> and api.<domain> at this host.
    3. Run ./scripts/setup-ssl.sh api.<domain> you@example.com
    4. Create the first admin:
       docker compose -f docker-compose.prod.yml --env-file .env.production \\
           exec backend python -m app.scripts.bootstrap_admin

==========================================

EOF
}

main() {
    validate
    preflight_local
    erp_step "Deploying ${VERSION} to ${TARGET} (${MODE})"

    if [ "${DRY_RUN}" != true ]; then
        preflight_remote
    fi
    sync_tree

    case "${MODE}" in
        push-only)  erp_info "push-only: tree synced, no services touched" ;;
        bootstrap)  remote_bootstrap ;;
        blue-green) remote_blue_green ;;
    esac

    print_summary
}

main "$@"