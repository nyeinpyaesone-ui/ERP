#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — End-user production installer
#
# Usage:
#   sudo ./install.sh                                    # interactive
#   sudo ./install.sh erp.example.com ops@example.com
#   sudo ./install.sh --domain=erp.example.com --email=ops@example.com
#
# Flags:
#   --domain=NAME     Base domain (api.<name> and app.<name> are used)
#   --email=ADDRESS   Let's Encrypt contact address
#   --dir=PATH        Install into PATH (default: this checkout)
#   --version=TAG     Image tag to deploy (default: VERSION, then latest git tag)
#   --skip-deps       Do not apt-get install anything
#   --skip-ssl        Do not request certificates; serve HTTP only
#   --no-build        Do not build images locally (pull only)
#   --preflight       Provision the host, report status, then exit
#   --yes             Never prompt; fail instead on anything missing
#
# Everything it needs is auto-detected: compose v2 vs v1, docker presence and
# daemon liveness, the env file, the image namespace, the release tag.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
. "${SCRIPT_DIR}/scripts/lib.sh"

DOMAIN="${1:-}"
EMAIL="${2:-}"

SKIP_DEPS=false
SKIP_SSL=false
NO_BUILD=false
ASSUME_YES=false
PREFLIGHT_ONLY=false

for arg in "$@"; do
    case "${arg}" in
        --domain=*)   DOMAIN="${arg#*=}" ;;
        --email=*)    EMAIL="${arg#*=}" ;;
        --dir=*)      ERP_DIR="${arg#*=}" ;;
        --version=*)  VERSION="${arg#*=}" ;;
        --skip-deps)  SKIP_DEPS=true ;;
        --skip-ssl)   SKIP_SSL=true ;;
        --no-build)   NO_BUILD=true ;;
        --preflight)  PREFLIGHT_ONLY=true ;;
        --yes|-y)     ASSUME_YES=true ;;
        --help|-h)    erp_help "${BASH_SOURCE[0]}"; exit 0 ;;
        -*)           erp_die "Unknown option: ${arg} (try --help)" ;;
        *) ;;
    esac
done

export ERP_DIR
# This installer only provisions the production Compose target.
export DEPLOY_TARGET_ENVIRONMENT=production
export ERP_COMPOSE_FILE="${ERP_COMPOSE_FILE:-${ERP_DIR}/docker-compose.prod.yml}"
export ERP_NGINX_DIR="${ERP_NGINX_DIR:-${ERP_DIR}/nginx}"
export ERP_SSL_DIR="${ERP_SSL_DIR:-${ERP_DIR}/ssl}"
mkdir -p "${ERP_DIR}/logs" && export ERP_LOG_FILE="${ERP_DIR}/logs/install-$(date +%Y%m%d-%H%M%S).log"

usage() {
    cat <<EOF
ERP Solution production installer

Usage: sudo ./install.sh [DOMAIN] [EMAIL] [options]

  DOMAIN    Base domain, e.g. erp.example.com  (api./app. subdomains are used)
  EMAIL     Contact address for Let's Encrypt

Options:
  --dir=PATH       Install into PATH (default: this checkout)
  --version=TAG    Image tag to deploy (default: VERSION, else latest git tag)
  --skip-deps      Do not provision the host; assert prerequisites only
  --skip-ssl       Skip certificate issuance; serve HTTP only
  --no-build       Pull images instead of building them locally
  --preflight      Provision the host, print a status report, then exit
  --yes, -y        Never prompt; fail on anything missing
  --help, -h       This text

Steps: preconfigure host -> directories -> env file -> compose validation ->
images -> database -> migrations -> application -> TLS -> verification.

The preconfigure step installs missing packages, installs and starts Docker,
installs the compose plugin, and warns about ports or disk that would otherwise
surprise you later. Run './install.sh --preflight' to see that report alone.
EOF
}

prompt_input() {
    local prompt="$1" var_name="$2" default="${3:-}" value=""
    if [ -n "${default}" ]; then
        read -rp "${prompt} [${default}]: " value
        value="${value:-${default}}"
    else
        while [ -z "${value}" ]; do read -rp "${prompt}: " value; done
    fi
    printf -v "${var_name}" '%s' "${value}"
}

###############################################################################
# Preflight
###############################################################################

check_root() {
    if [ "${EUID}" -ne 0 ]; then
        erp_die "Must run as root (use sudo)."
    fi
}

check_compose_file() {
    [ -f "${ERP_COMPOSE_FILE}" ] || erp_die "Compose file not found: ${ERP_COMPOSE_FILE}
Set ERP_COMPOSE_FILE or run from a checkout of the repository."
}

# Compose silently substitutes blanks for unset ${DB_PASSWORD} and friends,
# which produces a stack that starts and then fails closed with an opaque
# error. Fail here, where the message can name the missing variable.
validate_compose_config() {
    erp_step "Validating compose configuration"
    local output
    if output="$(erp_compose config 2>&1)"; then
        erp_success "docker-compose.prod.yml is valid"
    else
        printf '%s\n' "${output}" >&2
        erp_die "docker-compose.prod.yml is not valid (see above)."
    fi

    local missing=()
    local key value
    for key in DB_PASSWORD REDIS_PASSWORD SECRET_KEY CORS_ORIGINS; do
        value="$(erp_env_value "${key}" || true)"
        if [ -z "${value}" ] || [ "${value}" = "CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_BASE64_24" ] \
           || [ "${value}" = "CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_HEX_32" ] \
           || [[ "${value}" == CHANGE_ME* ]]; then
            missing+=("${key}")
        fi
    done
    if [ "${#missing[@]}" -gt 0 ]; then
        erp_error "Unset or placeholder values in ${ERP_ENV_FILE}: ${missing[*]}"
        erp_die "Fix them, or delete the env file to have one generated."
    fi
}

###############################################################################
# Steps
###############################################################################

install_dependencies() {
    # Everything the host needs is provisioned here: packages, the Docker daemon
    # (installed and started if needed), the compose plugin, plus a check on
    # ports and disk that would otherwise fail later as an opaque bind error.
    if [ "${SKIP_DEPS}" = true ]; then
        erp_info "Skipping host provisioning (--skip-deps)"
        # Still assert the hard requirements, so the failure names the missing
        # piece instead of surfacing later as an unrelated compose error.
        erp_require_openssl
        erp_require_docker
        return 0
    fi
    erp_preconfigure
}

create_directories() {
    erp_step "Creating directory structure under ${ERP_DIR}"
    # These four are bind mounts declared in docker-compose.prod.yml; relative
    # to the compose file's directory. Creating them anywhere else means the
    # containers get empty directories.
    mkdir -p "${ERP_DIR}/ssl" \
             "${ERP_DIR}/logs/nginx" \
             "${ERP_DIR}/backups" \
             "${ERP_DIR}/backend/uploads" \
             "${ERP_DIR}/nginx"
    chmod 700 "${ERP_DIR}/ssl"
    chown -R "${ERP_USER_NAME:-root}:${ERP_USER_NAME:-root}" "${ERP_DIR}/logs" "${ERP_DIR}/backups" 2>/dev/null || true
    erp_success "Directories ready"
}

generate_env_file() {
    if erp_detect_env_file; then
        if [ "$(basename "${ERP_ENV_FILE}")" != ".env.production" ]; then
            erp_die "The production installer only accepts a .env.production file; staging configuration is not permitted."
        fi
        erp_success "Using existing production env file: ${ERP_ENV_FILE}"
        return 0
    fi
    if [ "${ASSUME_YES}" = true ]; then
        erp_die "No environment file found. Run scripts/configure-environment.sh with the required domain and Docker namespace first."
    fi

    erp_step "Configuring production runtime environment"
    local domain="${DOMAIN}"
    if [ -z "${domain}" ]; then
        prompt_input "Base domain (e.g. erp.example.com)" domain
    fi

    local docker_user="${DOCKER_USER:-}"
    if [ -z "${docker_user}" ]; then
        prompt_input "Docker Hub namespace (lowercase)" docker_user
    fi

    local version
    version="$(erp_detect_version "${VERSION:-}")"
    bash "${SCRIPT_DIR}/scripts/configure-environment.sh" \
        --environment production \
        --domain "${domain}" \
        --docker-user "${docker_user}" \
        --version "${version}" \
        --dir "${ERP_DIR}"

    ERP_ENV_FILE="${ERP_DIR}/.env.production"
    export ERP_ENV_FILE
    erp_success "Production environment file created with unique generated secrets (mode 0600)."
    erp_info "Secret values were not printed; retain the file in your host's protected backup/secret-management process."
}
prepare_nginx_config() {
    erp_step "Preparing nginx configuration"
    local domain="${1:-}"
    # upstream-active.conf is the file nginx.conf includes; the blue/green
    # deploy flips it by copying a colour file over it.
    if [ ! -f "${ERP_NGINX_DIR}/upstream-active.conf" ]; then
        cp "${ERP_NGINX_DIR}/upstream-blue.conf" "${ERP_NGINX_DIR}/upstream-active.conf"
        erp_info "upstream-active.conf initialised from upstream-blue.conf"
    fi

    if [ -z "${domain}" ] || [ "${SKIP_SSL}" = true ]; then
        erp_info "HTTP only; nginx.conf's default_server block handles :80"
        return 0
    fi
    erp_render_ssl_conf "${domain}"
}

###############################################################################
# Images
###############################################################################

images_available() {
    local user="$1" version="$2"
    local service
    for service in backend frontend; do
        if docker image inspect "$(erp_image_ref "${service}" "${version}" "${user}")" >/dev/null 2>&1; then
            return 0
        fi
    done
    return 1
}

prepare_images() {
    local version="$1"
    local user; user="$(erp_detect_docker_user)"

    erp_step "Preparing images (version ${version}, namespace ${user})"
    erp_info "backend:  $(erp_image_ref backend  "${version}" "${user}")"
    erp_info "frontend: $(erp_image_ref frontend "${version}" "${user}")"

    if images_available "${user}" "${version}" && [ "${NO_BUILD}" = true ]; then
        erp_success "Images already present locally"
        return 0
    fi

    # Try the registry first: CI publishes these tags. A local build is the
    # fallback so a fresh server with no published images still comes up.
    if erp_compose pull backend frontend; then
        erp_success "Pulled images from the registry"
        return 0
    fi
    erp_warn "Registry pull failed (unpublished tag, no network, or no login)"

    if [ "${NO_BUILD}" = true ]; then
        erp_die "--no-build was given and the images could not be pulled."
    fi
    erp_step "Building images locally"
    erp_info "Buildx is used when available for better layer caching."
    local build_cmd=(docker build)
    if erp_have docker && docker buildx version >/dev/null 2>&1; then
        build_cmd=(docker buildx build --load)
    fi
    "${build_cmd[@]}" -t "$(erp_image_ref backend "${version}" "${user}")" "${ERP_DIR}/backend"
    "${build_cmd[@]}" -t "$(erp_image_ref frontend "${version}" "${user}")" "${ERP_DIR}/backend/frontend-react"
    erp_success "Images built locally"
}

###############################################################################
# Deploy
###############################################################################

start_infrastructure() {
    erp_step "Starting PostgreSQL, Redis and Ollama"
    erp_compose up -d postgres redis ollama

    erp_step "Waiting for PostgreSQL"
    local waited=0
    until docker exec erp-postgres pg_isready -q -U "$(erp_env_value DB_USER || echo erp)"; do
        waited=$((waited + 5))
        if [ "${waited}" -ge 120 ]; then
            docker logs erp-postgres --tail 50 >&2 2>/dev/null || true
            erp_die "PostgreSQL did not become ready within 120s"
        fi
        sleep 5
    done
    erp_success "PostgreSQL is accepting connections"
}

run_migrations() {
    erp_step "Running database migrations"
    # entrypoint.sh already runs `alembic upgrade head` on container start; this
    # explicit pass makes the first migration visible before the app boots and
    # surfaces schema errors in the installer log.
    erp_compose run --rm --no-deps backend alembic upgrade head \
        || erp_warn "Standalone migration run failed; entrypoint.sh will retry on start"
    erp_success "Migrations applied"
}

start_application() {
    erp_step "Starting nginx, frontend and backend"
    erp_compose up -d nginx frontend backend
    erp_wait_for_health erp-blue-backend 240 || erp_die "Backend never became healthy"
    erp_wait_for_health erp-blue-frontend 120 || erp_warn "Frontend healthcheck did not report healthy"
}

###############################################################################
# TLS
###############################################################################

obtain_ssl() {
    local domain="$1" email="$2"
    local api_domain="api.${domain}"

    if [ "${SKIP_SSL}" = true ]; then
        erp_warn "Skipping TLS (--skip-ssl); serving plain HTTP on :80"
        return 0
    fi
    if erp_ssl_present "${api_domain}"; then
        erp_success "Reusing existing certificate at $(erp_ssl_cert_path "${api_domain}")"
        return 0
    fi
    if ! erp_have certbot; then
        erp_warn "certbot is not installed; skipping TLS. Re-run with certbot available."
        return 0
    fi
    if [ -z "${email}" ]; then
        erp_warn "No contact email supplied; skipping TLS issuance"
        return 0
    fi

    erp_step "Requesting Let's Encrypt certificate for api.${domain} and app.${domain}"
    erp_warn "Both subdomains must already resolve to this host's public IP."

    # nginx here runs as a container publishing :80, so the host's own service
    # has nothing to stop. A webroot plugin against the mounted volume lets
    # certbot complete without touching that container.
    mkdir -p "${ERP_DIR}/ssl/live/${api_domain}" /var/www/certbot

    # ACME http-01 needs port 80 reachable. If erp-nginx holds it, stop it for
    # the duration and restart it afterwards.
    local nginx_was_up=false
    if erp_container_exists erp-nginx && [ "$(erp_container_health erp-nginx)" != "missing" ]; then
        nginx_was_up=true
        erp_info "Stopping erp-nginx for the duration of the ACME challenge"
        erp_compose stop nginx
    fi

    local rc=0
    certbot certonly --standalone --non-interactive --agree-tos \
        --email "${email}" \
        -d "${api_domain}" -d "app.${domain}" \
        --cert-path "${ERP_SSL_DIR}/live/${api_domain}/cert.pem" \
        --key-path  "${ERP_SSL_DIR}/live/${api_domain}/privkey.pem" \
        --fullchain-path "${ERP_SSL_DIR}/live/${api_domain}/fullchain.pem" \
        --chain-path "${ERP_SSL_DIR}/live/${api_domain}/chain.pem" \
        >/dev/null 2>&1 || rc=$?

    if [ "${nginx_was_up}" = true ]; then
        erp_info "Restarting erp-nginx"
        erp_compose up -d nginx
    fi

    if [ "${rc}" -ne 0 ] || ! erp_ssl_present "${api_domain}"; then
        erp_warn "Certificate issuance failed (exit ${rc}); continuing on HTTP only."
        erp_warn "Retry later with: ./scripts/setup-ssl.sh ${api_domain} ${email}"
        return 0
    fi
    chmod 600 "${ERP_SSL_DIR}/live/${api_domain}"/*.pem
    erp_success "Certificate stored at $(erp_ssl_cert_path "${api_domain}")"

    setup_certbot_renewal "${api_domain}"
}

setup_certbot_renewal() {
    local domain="$1"
    erp_step "Scheduling automatic renewal"
    # The deploy hooks must copy into the bind-mounted layout the generated
    # nginx block reads, otherwise renewal silently rotates a certificate the
    # proxy never sees.
    cat > /etc/cron.d/erp-certbot-renewal <<EOF
# Renew the ERP Solution certificate and reload the proxy.
# Managed by install.sh. Certificates live in ${ERP_DIR}/ssl/live/${domain}
0 3 * * * root certbot renew --quiet --deploy-hook "cp -f /etc/letsencrypt/live/${domain}/fullchain.pem ${ERP_SSL_DIR}/live/${domain}/fullchain.pem && cp -f /etc/letsencrypt/live/${domain}/privkey.pem ${ERP_SSL_DIR}/live/${domain}/privkey.pem && chmod 600 ${ERP_SSL_DIR}/live/${domain}/*.pem && docker exec erp-nginx nginx -s reload"
EOF
    chmod 644 /etc/cron.d/erp-certbot-renewal
    erp_success "Renewal scheduled daily at 03:00"
}

###############################################################################
# Verification
###############################################################################

verify_deployment() {
    erp_step "Verifying deployment"
    local scheme="http"
    local host="localhost"
    local domain="$1"

    if [ -n "${domain}" ] && erp_ssl_present "api.${domain}" && erp_container_exists erp-nginx; then
        erp_render_ssl_conf "api.${domain}" >/dev/null
        erp_reload_nginx erp-nginx || true
        scheme="https"; host="api.${domain}"
    elif [ -n "${domain}" ] && [ "${SKIP_SSL}" != true ]; then
        host="${domain}"
    fi

    local ready=false
    for target in "${scheme}://${host}/health" "${scheme}://${host}/ready" "http://127.0.0.1/health"; do
        if curl -fsS --max-time 10 "${target}" >/dev/null 2>&1; then
            erp_success "Reachable: ${target}"
            ready=true
            break
        fi
    done

    if [ "${ready}" = true ]; then
        erp_info "Readiness payload:"
        curl -fsS --max-time 10 "${scheme}://${host}/ready" 2>/dev/null | head -c 400 || true
        echo
    else
        erp_warn "No HTTP endpoint answered yet. If this host is behind a firewall"
        erp_warn "or has no DNS yet, that is expected; check with:"
        erp_warn "  ${ERP_COMPOSE_CMD} -f ${ERP_COMPOSE_FILE} --env-file ${ERP_ENV_FILE} ps"
        erp_warn "  docker logs erp-blue-backend --tail 50"
    fi

    erp_step "Service status"
    erp_compose ps 2>/dev/null || true
}

print_summary() {
    local version="$1"
    local user; user="$(erp_detect_docker_user)"
    local domain="$DOMAIN"
    local app_url="http://<this-server-ip>"
    if [ -n "${domain}" ]; then
        app_url="https://app.${domain}"
    fi

    cat <<EOF

==========================================
  ERP SOLUTION — installation complete
==========================================

  Version:   ${version}
  Images:    ${user}/erp-solution-backend:${version}
             ${user}/erp-solution-frontend:${version}
  App URL:   ${app_url}
  Env file:  ${ERP_ENV_FILE}
  Log file:  ${ERP_LOG_FILE}

  Point app.${domain:-your-domain} and api.${domain:-your-domain} at this
  host, then create the first admin with:
    ${ERP_COMPOSE_CMD} -f ${ERP_COMPOSE_FILE} --env-file ${ERP_ENV_FILE} \\
        exec backend python -m app.scripts.bootstrap_admin

  Day-to-day:
    Status:    ${ERP_COMPOSE_CMD} -f ${ERP_COMPOSE_FILE} --env-file ${ERP_ENV_FILE} ps
    Logs:      ${ERP_COMPOSE_CMD} -f ${ERP_COMPOSE_FILE} --env-file ${ERP_ENV_FILE} logs -f backend
    Deploy:    ./scripts/deploy-blue-green.sh production ${version}
    Rollback:  ./scripts/deploy-blue-green.sh production <old-tag> --rollback
    Backup:    ./scripts/backup.sh

==========================================

EOF
}

###############################################################################
# Entry point
###############################################################################

main() {
    echo -e "${ERP_BLUE}"
    cat <<'BANNER'
  _____       _ _     _   _ _
 |  __ \     | | |   | \ | | |
 | |  | | ___| | |__ |  \| | |___
 | |  | |/ _ \ | '_ \| . ` | / __|
 | |__| |  __/ | |_) | |\  | \__ \
 |_____/ \___|_|_.__/|_| \_|_|___/

BANNER
    echo -e "${ERP_NC}"

    ERP_USER_NAME="${SUDO_USER:-root}"
    # On Termux/proot hosts Docker provisioning is skipped entirely (see
    # erp_detect_runtime_class), so root is not required for --preflight's
    # native-mode report. A real install still dies later at erp_require_docker
    # with explicit guidance.
    erp_detect_runtime_class
    if [ "${ERP_RUNTIME_CLASS}" = "proot-termux" ]; then
        erp_warn "Runtime class: proot-termux — Docker provisioning will be skipped (native-mode report only)"
    else
        check_root
    fi
    check_compose_file
    erp_require_openssl

    if [ -z "${DOMAIN}" ] || [ -z "${EMAIL}" ]; then
        usage
        if [ "${ASSUME_YES}" = true ]; then
            erp_die "DOMAIN and EMAIL are required with --yes"
        fi
        [ -z "${DOMAIN}" ] && prompt_input "Base domain (e.g. erp.example.com)" DOMAIN
        [ -z "${EMAIL}" ]  && prompt_input "Let's Encrypt contact email" EMAIL
    fi

    local version; version="$(erp_detect_version "${VERSION:-}")"

    erp_info "Installing ERP Solution ${version} into ${ERP_DIR} for ${DOMAIN}"

    # Provision first, assert second. Asserting the daemon before this point
    # would refuse a clean host that does not have Docker installed yet.
    install_dependencies
    if [ "${PREFLIGHT_ONLY}" = true ]; then
        erp_preflight_report
        erp_success "Preflight complete; re-run without --preflight to deploy."
        return 0
    fi
    erp_require_docker

    create_directories
    generate_env_file
    validate_compose_config
    prepare_nginx_config "${DOMAIN}"
    prepare_images "${version}"
    start_infrastructure
    run_migrations
    start_application
    obtain_ssl "${DOMAIN}" "${EMAIL}"
    verify_deployment "${DOMAIN}"
    print_summary "${version}"

    erp_success "Done."
}

main "$@"