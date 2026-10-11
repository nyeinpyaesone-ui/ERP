#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Shared shell helpers
# Sourced by install.sh, deploy.sh, docker-build.sh and scripts/*.sh.
# Never executed directly. Safe under `set -euo pipefail`.
#
# Everything here is auto-detected rather than hardcoded, because the three
# entrypoint scripts run in two very different places: a developer laptop and
# a clean production host. Detected once, cached in a variable, reused.
###############################################################################

# Repo root. Works whether this is sourced from the repo root or from scripts/.
ERP_PROJECT_ROOT="${ERP_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# Where the running install lives. The compose file bind-mounts ./ssl,
# ./logs/nginx, ./backups and ./backend/uploads relative to ITS OWN directory,
# so this must be the directory that actually holds docker-compose.prod.yml —
# not a hardcoded /opt/erp-solution. Override with ERP_DIR=... when the repo
# is deployed elsewhere.
ERP_DIR="${ERP_DIR:-${ERP_PROJECT_ROOT}}"

ERP_COMPOSE_FILE="${ERP_COMPOSE_FILE:-${ERP_DIR}/docker-compose.prod.yml}"
ERP_NGINX_DIR="${ERP_NGINX_DIR:-${ERP_DIR}/nginx}"
ERP_SSL_DIR="${ERP_SSL_DIR:-${ERP_DIR}/ssl}"

# Fallback image namespace when neither the environment nor the env file says.
ERP_DEFAULT_DOCKER_USER="${ERP_DEFAULT_DOCKER_USER:-powerrangeranikg}"

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    ERP_RED='\033[0;31m'; ERP_GREEN='\033[0;32m'; ERP_YELLOW='\033[1;33m'
    ERP_BLUE='\033[0;34m'; ERP_CYAN='\033[0;36m'; ERP_NC='\033[0m'
else
    ERP_RED=''; ERP_GREEN=''; ERP_YELLOW=''; ERP_BLUE=''; ERP_CYAN=''; ERP_NC=''
fi

ERP_LOG_FILE="${ERP_LOG_FILE:-}"

erp_log() {
    local level="$1"; shift
    local line
    line="$(date '+%Y-%m-%d %H:%M:%S') [${level}] $*"
    if [ -n "${ERP_LOG_FILE}" ]; then
        mkdir -p "$(dirname "${ERP_LOG_FILE}")" 2>/dev/null || true
        printf '%b\n' "${line}" >> "${ERP_LOG_FILE}"
    fi
    printf '%b\n' "${line}"
}
erp_info()    { erp_log INFO    "${ERP_BLUE}$*${ERP_NC}"; }
erp_success() { erp_log SUCCESS "${ERP_GREEN}$*${ERP_NC}"; }
erp_warn()    { erp_log WARN    "${ERP_YELLOW}$*${ERP_NC}"; }
erp_error()   { erp_log ERROR   "${ERP_RED}$*${ERP_NC}" >&2; }
erp_step()    { erp_log INFO    "${ERP_CYAN}==>${ERP_NC} $*"; }
erp_die()     { erp_error "$*"; exit 1; }

erp_have() { command -v "$1" >/dev/null 2>&1; }

erp_require_cmd() {
    erp_have "$1" || erp_die "Required command not found: $1${2:+ ($2)}"
}

# Print a script's leading comment block as usage text. Reads only the comment
# run at the top of the file, strips the shebang and the rule lines, and stops
# at the first line of code — so it can never spill into the implementation the
# way a fixed `sed -n '2,25p'` range does.
erp_help() {
    local script="${1:-$0}"
    awk '
        NR == 1 && /^#!/ { next }
        /^#/ {
            line = $0
            sub(/^#[[:space:]]?/, "", line)
            if (line ~ /^#+$/) {                 # rule line
                if (started) { exit }            # closing rule ends the block
                next                             # opening rule is skipped
            }
            started = 1
            print line
            next
        }
        { exit }
    ' "${script}" | grep -v '^$'
}

###############################################################################
# Docker / Compose detection
###############################################################################

# Compose v2 plugin (`docker compose`) is the only supported form; the v1
# `docker-compose` shim was removed from modern Docker packages and its
# GitHub download URL is a moving target. v1 is still accepted so an older
# host keeps working, but v2 is tried first.
erp_detect_compose() {
    [ -n "${ERP_COMPOSE_CMD:-}" ] && return 0
    if docker compose version >/dev/null 2>&1; then
        ERP_COMPOSE_CMD="docker compose"
    elif erp_have docker-compose && docker-compose version >/dev/null 2>&1; then
        erp_warn "Only docker-compose v1 found. Install the v2 plugin: apt-get install docker-compose-plugin"
        ERP_COMPOSE_CMD="docker-compose"
    else
        return 1
    fi
    return 0
}

# `docker info` is the only reliable liveness probe for the daemon; every other
# subcommand can succeed against a socket that has no engine behind it.
erp_require_docker() {
    erp_require_cmd docker
    erp_detect_compose || erp_die "Neither 'docker compose' nor 'docker-compose' is available"
    if ! docker info >/dev/null 2>&1; then
        erp_die "Docker daemon is not reachable. Start it first (e.g. 'sudo systemctl start docker') and retry."
    fi
}

erp_compose() {
    erp_detect_compose || erp_die "docker compose is not available"
    if [ -n "${ERP_ENV_FILE:-}" ]; then
        ${ERP_COMPOSE_CMD} --env-file "${ERP_ENV_FILE}" -f "${ERP_COMPOSE_FILE}" "$@"
    else
        ${ERP_COMPOSE_CMD} -f "${ERP_COMPOSE_FILE}" "$@"
    fi
}

###############################################################################
# Environment file handling
###############################################################################

# Auto-detect in priority order: explicit override, production env file, dev
# env file, then plain environment variables.
erp_detect_env_file() {
    if [ -n "${ERP_ENV_FILE:-}" ]; then
        [ -f "${ERP_ENV_FILE}" ] || erp_die "ERP_ENV_FILE set but missing: ${ERP_ENV_FILE}"
        return 0
    fi
    local candidate
    for candidate in \
        "${ERP_DIR}/.env.production" \
        "${ERP_PROJECT_ROOT}/.env.production" \
        "${ERP_PROJECT_ROOT}/.env" \
        "${ERP_DIR}/.env"
    do
        if [ -f "${candidate}" ]; then
            ERP_ENV_FILE="${candidate}"
            return 0
        fi
    done
    return 1
}

# Line parser instead of `source`: a .env file is data, not shell, and a value
# containing a space, a quote or a `$` must not be able to execute anything or
# silently truncate. Only well-formed KEY=VALUE lines are accepted.
erp_load_env() {
    local file="${1:-${ERP_ENV_FILE:-}}"
    [ -f "${file}" ] || return 1
    local line key value
    while IFS= read -r line || [ -n "${line}" ]; do
        line="${line%$'\r'}"
        case "${line}" in
            ''|'#'*) continue ;;
            export\ *) line="${line#export }" ;;
        esac
        case "${line}" in
            [A-Za-z_]*=*) ;;
            *) continue ;;
        esac
        key="${line%%=*}"
        value="${line#*=}"
        # Strip one layer of matching quotes, then trailing inline comment.
        case "${value}" in
            \"*\") value="${value#\"}"; value="${value%\"}" ;;
            \'*\') value="${value#\'}"; value="${value%\'}" ;;
        esac
        value="${value%%#*}"
        export "${key}=$(printf '%s' "${value}" | sed -e 's/[[:space:]]*$//')"
    done < "${file}"
    return 0
}

# Read one key without polluting the environment.
erp_env_value() {
    local key="$1" file="${2:-${ERP_ENV_FILE:-}}"
    [ -f "${file}" ] || return 1
    sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" "${file}" \
        | tail -n 1 \
        | sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"
}

erp_detect_docker_user() {
    if [ -n "${DOCKER_USER:-}" ]; then
        echo "${DOCKER_USER}"; return 0
    fi
    local value
    if value="$(erp_env_value DOCKER_USER)"; then
        [ -n "${value}" ] && { echo "${value}"; return 0; }
    fi
    echo "${ERP_DEFAULT_DOCKER_USER}"
}

# Release resolution: explicit argument, then VERSION from the environment,
# then the most recent git tag, then `latest`. CI pushes `vX.Y.Z` tags, so a
# tag-derived version keeps this script in step with what the images carry.
erp_detect_version() {
    local version="${1:-}"
    [ -n "${version}" ] && { echo "${version}"; return 0; }
    [ -n "${VERSION:-}" ] && { echo "${VERSION}"; return 0; }
    if erp_have git && version="$(git -C "${ERP_PROJECT_ROOT}" describe --tags --abbrev=0 2>/dev/null)"; then
        [ -n "${version}" ] && { echo "${version}"; return 0; }
    fi
    echo "latest"
}

erp_image_ref() {
    local service="$1" version="$2" user="$3"
    echo "${user}/erp-solution-${service}:${version}"
}

###############################################################################
# Secrets
###############################################################################

erp_require_openssl() { erp_require_cmd openssl "apt-get install -y openssl"; }

erp_random_hex()    { openssl rand -hex "${1:-32}"; }
erp_random_secret() { openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | cut -c1-48; }

###############################################################################
# Preconfiguration
#
# Everything an installation needs, provisioned automatically and idempotently:
# packages, the Docker daemon, the compose plugin, host directories and the
# checks that predict a failure before it happens (ports already bound, not
# enough disk). Safe to run on a host that is already fully set up.
###############################################################################

# Packages split by need. The first group is required for the install to
# complete; the second only enables optional paths (TLS, further rsync deploys)
# so a missing certbot must not abort a working HTTP-only deployment.
ERP_PKGS_REQUIRED=(curl ca-certificates openssl)
ERP_PKGS_OPTIONAL=(gnupg rsync certbot)

erp_apt() {
    DEBIAN_FRONTEND=noninteractive apt-get "$@"
}

erp_ensure_packages() {
    local missing=()
    local pkg
    for pkg in "${ERP_PKGS_REQUIRED[@]}"; do
        erp_have "${pkg}" || missing+=("${pkg}")
    done
    if [ "${#missing[@]}" -gt 0 ]; then
        erp_have apt-get || erp_die "Missing ${missing[*]} and no apt-get to install them."
        erp_step "Installing required packages: ${missing[*]}"
        erp_apt update -qq
        # shellcheck disable=SC2086
        erp_apt install -y -qq ${missing[@]} >/dev/null \
            || erp_die "apt-get install failed for: ${missing[*]}"
    fi

    local optional=()
    for pkg in "${ERP_PKGS_OPTIONAL[@]}"; do
        erp_have "${pkg}" || optional+=("${pkg}")
    done
    if [ "${#optional[@]}" -gt 0 ] && erp_have apt-get; then
        erp_info "Installing optional packages: ${optional[*]}"
        # shellcheck disable=SC2086
        erp_apt install -y -qq ${optional[@]} >/dev/null 2>&1 \
            || erp_warn "Optional packages unavailable: ${optional[*]} (TLS and rsync deploys will be skipped)"
    fi
}

erp_ensure_docker() {
    if ! erp_have docker; then
        erp_step "Installing Docker Engine"
        curl -fsSL https://get.docker.com | sh >/dev/null \
            || erp_die "Docker installation failed. Install Docker manually and re-run."
        systemctl enable --now docker >/dev/null 2>&1 || true
    fi

    # The binary can be present while the daemon is stopped, which is the state
    # on most freshly imaged hosts. Start it rather than reporting a dead end.
    if ! docker info >/dev/null 2>&1; then
        erp_warn "Docker is installed but the daemon is not answering; starting it"
        systemctl start docker >/dev/null 2>&1 || service docker start >/dev/null 2>&1 || true
        local waited=0
        while [ "${waited}" -lt 30 ] && ! docker info >/dev/null 2>&1; do
            sleep 2
            waited=$((waited + 2))
        done
    fi
    docker info >/dev/null 2>&1 \
        || erp_die "The Docker daemon is still not reachable. Start it (systemctl start docker) and re-run."
    erp_success "Docker daemon is up"
}

erp_ensure_compose() {
    [ -n "${ERP_COMPOSE_CMD:-}" ] && return 0
    erp_detect_compose && { erp_success "Compose available: ${ERP_COMPOSE_CMD}"; return 0; }

    erp_step "Installing the docker compose v2 plugin"
    if erp_have apt-get; then
        erp_apt install -y -qq docker-compose-plugin >/dev/null 2>&1 || true
    fi
    if ! erp_detect_compose; then
        # Last resort: the standalone binary. Its download URL tracks releases,
        # so it stays correct where a pinned URL would rot.
        local url="https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)"
        if curl -fsSL "${url}" -o /usr/local/bin/docker-compose; then
            chmod +x /usr/local/bin/docker-compose
        else
            erp_die "Could not install docker compose. Install it manually: https://docs.docker.com/compose/install/"
        fi
        unset ERP_COMPOSE_CMD
        erp_detect_compose || erp_die "Compose is still unavailable after installation"
    fi
    erp_success "Compose available: ${ERP_COMPOSE_CMD}"
}

# Name whatever is listening on a TCP port, if anything. ss is preferred; it is
# present on every current Debian/Ubuntu image, and lsof is the fallback.
erp_port_holder() {
    local port="$1"
    if erp_have ss; then
        ss -ltnp 2>/dev/null | awk -v p=":${port}\$" '$4 ~ p {print $NF}' | head -n1
    elif erp_have lsof; then
        lsof -ti ":${port}" -sTCP:LISTEN 2>/dev/null | head -n1
    fi
}

# erp-nginx publishes 80 and 443. Anything else already holding those ports
# makes `compose up` fail with a bind error that names neither the process nor
# the port, so identify the holder up front.
ERP_REQUIRED_PORTS=(80 443)

erp_check_ports() {
    local conflicts=0 port holder
    for port in "${ERP_REQUIRED_PORTS[@]}"; do
        holder="$(erp_port_holder "${port}")"
        if [ -n "${holder}" ]; then
            erp_warn "Port ${port} is already in use by: ${holder}"
            conflicts=$((conflicts + 1))
        fi
    done
    if [ "${conflicts}" -gt 0 ]; then
        erp_warn "erp-nginx publishes ${ERP_REQUIRED_PORTS[*]}. Stop the other listener,"
        erp_warn "or change the published ports in docker-compose.prod.yml, then re-run."
    fi
    return 0
}

erp_check_disk() {
    local needed_kb=2097152   # 2 GB: images plus a Postgres volume
    local avail_kb
    avail_kb="$(df -Pk "${ERP_DIR}" 2>/dev/null | awk 'NR==2 {print $4}')"
    [ -z "${avail_kb}" ] && return 0
    if [ "${avail_kb}" -lt "${needed_kb}" ]; then
        erp_warn "Only $((avail_kb / 1024)) MB free on the filesystem holding ${ERP_DIR};"
        erp_warn "at least 2 GB is needed for the images and the database volume."
    fi
    return 0
}

erp_check_host() {
    if erp_have curl && [ -s /etc/os-release ]; then
        erp_info "Host: $(. /etc/os-release && echo "${PRETTY_NAME:-unknown}") | $(uname -m) | $(nproc) cores"
    fi
    erp_check_ports
    erp_check_disk
}

# One call that leaves the host ready to install. Idempotent: on a host that is
# already provisioned it only re-checks.
erp_preconfigure() {
    erp_step "Preconfiguring host"
    erp_ensure_packages
    erp_ensure_docker
    erp_ensure_compose
    erp_check_host
    erp_success "Host is ready"
}

# Diagnostics without changing anything beyond provisioning. `--preflight`
# callers get this, so an operator can see what is missing before committing.
erp_preflight_report() {
    erp_step "Preflight report"
    local line
    for line in \
        "openssl:$(erp_have openssl && echo ok || echo MISSING)" \
        "curl:$(erp_have curl && echo ok || echo MISSING)" \
        "docker:$(erp_have docker && echo ok || echo MISSING)" \
        "docker-daemon:$(docker info >/dev/null 2>&1 && echo ok || echo DOWN)" \
        "compose:$(erp_detect_compose && echo "${ERP_COMPOSE_CMD}" || echo MISSING)" \
        "rsync:$(erp_have rsync && echo ok || echo MISSING)" \
        "certbot:$(erp_have certbot && echo ok || echo MISSING)" \
        "compose-file:$([ -f "${ERP_COMPOSE_FILE}" ] && echo ok || echo MISSING)" \
        "nginx-dir:$([ -d "${ERP_NGINX_DIR}" ] && echo ok || echo MISSING)"
    do
        erp_info "  ${line%%:*}: ${line#*:}"
    done
    if erp_detect_env_file; then
        erp_info "  env-file: ${ERP_ENV_FILE}"
    else
        erp_info "  env-file: none yet (install.sh will generate one)"
    fi
}

###############################################################################
# Container helpers
###############################################################################

erp_container_exists() { docker inspect "$1" >/dev/null 2>&1; }

erp_container_health() {
    docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$1" 2>/dev/null || echo "missing"
}

# Poll a container's healthcheck instead of sleeping a fixed interval: the
# backend entrypoint waits for Postgres and Redis and then runs Alembic, so its
# start time is highly variable.
erp_wait_for_health() {
    local container="$1" timeout="${2:-180}"
    local waited=0
    erp_info "Waiting for ${container} to become healthy (timeout ${timeout}s)..."
    while [ "${waited}" -lt "${timeout}" ]; do
        local status
        status="$(erp_container_health "${container}")"
        case "${status}" in
            healthy) erp_success "${container} is healthy"; return 0 ;;
            unhealthy)
                erp_error "${container} reports unhealthy"
                docker logs "${container}" --tail 50 >&2 2>/dev/null || true
                return 1
                ;;
            missing)
                erp_error "${container} does not exist"
                return 1
                ;;
        esac
        sleep 5
        waited=$((waited + 5))
    done
    erp_error "${container} did not become healthy within ${timeout}s"
    docker logs "${container}" --tail 100 >&2 2>/dev/null || true
    return 1
}

###############################################################################
# nginx TLS block
###############################################################################

# Single source of truth for the generated 443 server block. install.sh and
# scripts/setup-ssl.sh both call this, which is why a certificate obtained by
# one is immediately usable by the other: the certificate path here is the
# in-container path that docker-compose.prod.yml bind-mounts at
# /etc/nginx/ssl, and it matches the layout certbot is pointed at.
erp_render_ssl_conf() {
    local domain="$1"
    local out="${ERP_NGINX_DIR}/ssl.conf"
    mkdir -p "${ERP_NGINX_DIR}"
    cat > "${out}" <<EOF
# Auto-generated SSL config for ${domain}
# DO NOT EDIT MANUALLY - regenerate with ./install.sh or ./scripts/setup-ssl.sh

server {
    listen 80;
    server_name ${domain};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
        try_files \$uri =404;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    http2 on;
    server_name ${domain};

    ssl_certificate /etc/nginx/ssl/live/${domain}/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/live/${domain}/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' wss:;" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Rate limit zones are declared in nginx.conf.
    location ~ ^/api/v1/auth/(login|register) {
        limit_req zone=auth_limit burst=3 nodelay;
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Backend, including the WebSocket at /api/v1/ws. proxy_pass carries no
    # URI so the original path is forwarded unchanged.
    location /api {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
    }

    location /health {
        proxy_pass http://backend;
        access_log off;
    }

    location /ready {
        proxy_pass http://backend;
        access_log off;
    }

    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    erp_success "nginx TLS block written to ${out}"
}

# Validate the candidate configuration before reloading, so a typo can never
# take the running proxy down. Returns non-zero when nginx is not up yet.
erp_reload_nginx() {
    local container="${1:-erp-nginx}"
    if ! erp_container_exists "${container}"; then
        erp_warn "${container} is not running; skipping nginx reload"
        return 1
    fi
    if docker exec "${container}" nginx -t >/dev/null 2>&1; then
        docker exec "${container}" nginx -s reload >/dev/null 2>&1 \
            && { erp_success "nginx reloaded"; return 0; }
    fi
    erp_error "nginx configuration test failed"
    docker exec "${container}" nginx -t >&2 2>/dev/null || true
    return 1
}

erp_ssl_cert_path() { echo "${ERP_SSL_DIR}/live/$1/fullchain.pem"; }
erp_ssl_key_path()  { echo "${ERP_SSL_DIR}/live/$1/privkey.pem"; }

erp_ssl_present() {
    [ -f "$(erp_ssl_cert_path "$1")" ] && [ -f "$(erp_ssl_key_path "$1")" ]
}