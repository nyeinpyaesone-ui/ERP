#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Automated SSL Setup with Let's Encrypt
# Usage: ./scripts/setup-ssl.sh [domain] [email] [--staging]
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${SCRIPT_DIR}/lib.sh"
PROJECT_ROOT="${ERP_PROJECT_ROOT}"
NGINX_CONF_DIR="${ERP_NGINX_DIR}"
NGINX_CONF_FILE="${PROJECT_ROOT}/nginx.conf"
SSL_DIR="${ERP_SSL_DIR}"
# Path the same files have inside the erp-nginx container
# (docker-compose.prod.yml mounts <project>/ssl at /etc/nginx/ssl).
SSL_DIR_IN_CONTAINER="/etc/nginx/ssl"
mkdir -p "${ERP_DIR}/logs"
LOG_FILE="${ERP_DIR}/logs/ssl-setup-$(date +%Y%m%d-%H%M%S).log"
export ERP_LOG_FILE="${LOG_FILE}"

# Sensible defaults, but a placeholder domain must never be sent to Let's
# Encrypt: it would burn a rate-limit attempt on a name that cannot validate.
DOMAIN="${1:-}"
EMAIL="${2:-}"
STAGING="${3:-false}"

usage() {
    cat <<'USAGE'
Usage: ./scripts/setup-ssl.sh <domain> [email] [--staging]

  domain   Fully-qualified name to certify, e.g. api.erp.example.com
  email    Let's Encrypt contact address
  --staging  Use the Let's Encrypt staging environment (untrusted by browsers)

Certificates are written to <install>/ssl/live/<domain>/ and the nginx TLS
block is regenerated to match, so the running proxy picks them up on reload.

Examples:
  ./scripts/setup-ssl.sh api.erp.example.com ops@erp.example.com
  ./scripts/setup-ssl.sh api.erp.example.com ops@erp.example.com --staging
USAGE
}

for arg in "$@"; do
    case "${arg}" in
        --staging) STAGING=true ;;
        --help|-h) usage; exit 0 ;;
    esac
done

log()       { erp_log "$@"; }
info()      { erp_info "$@"; }
success()   { erp_success "$@"; }
warn()      { erp_warn "$@"; }
error()     { erp_error "$@"; }

cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        error "SSL setup failed with exit code $exit_code"
        error "Check log: ${LOG_FILE}"
    fi
    exit $exit_code
}
trap cleanup EXIT

validate_inputs() {
    info "Validating inputs..."

    if [ -z "${DOMAIN}" ] || [ -z "${EMAIL}" ]; then
        error "Both a domain and a contact email are required."
        usage
        exit 1
    fi
    if [[ "${DOMAIN}" == *"yourdomain"* ]] || [ "${EMAIL}" == *"yourdomain"* ]; then
        error "Refusing to request a certificate for the placeholder ${DOMAIN}."
        exit 1
    fi
    # A certificate has to be issued against a fully-qualified name, so the
    # value must contain a dot. "localhost" and bare hostnames cannot validate.
    case "${DOMAIN}" in
        *.*) ;;
        *)
            error "Not a fully-qualified domain: ${DOMAIN}"
            error "Pass the name including the subdomain, e.g. api.erp.example.com."
            exit 1
            ;;
    esac
    if [[ ! "${DOMAIN}" =~ ^[a-zA-Z0-9.-]+$ ]]; then
        error "Invalid domain format: ${DOMAIN}"
        exit 1
    fi
    
    if [[ ! "${EMAIL}" =~ ^[^@]+@[^@]+\.[^@]+$ ]]; then
        error "Invalid email format: ${EMAIL}"
        exit 1
    fi
    
    if [ ! -d "${SSL_DIR}" ]; then
        info "Creating SSL directory: ${SSL_DIR}"
        mkdir -p "${SSL_DIR}"
    fi
    
    if ! command -v certbot &> /dev/null; then
        info "Installing certbot..."
        apt-get update && apt-get install -y certbot python3-certbot-nginx
    fi
    
    success "Input validation passed"
}

generate_nginx_config() {
    # Single source of truth, shared with install.sh: a certificate obtained by
    # either script is immediately usable by the other, because the paths in
    # the generated block are the in-container ones the compose file mounts.
    info "Generating nginx TLS block for ${DOMAIN}..."
    erp_render_ssl_conf "${DOMAIN}"
}

obtain_certificate() {
    info "Obtaining SSL certificate for ${DOMAIN}..."
    
    local certbot_args=(
        certonly
        --nginx
        --non-interactive
        --agree-tos
        --email "${EMAIL}"
        --domains "${DOMAIN}"
        --cert-path "${SSL_DIR}/live/${DOMAIN}/cert.pem"
        --key-path "${SSL_DIR}/live/${DOMAIN}/privkey.pem"
        --fullchain-path "${SSL_DIR}/live/${DOMAIN}/fullchain.pem"
        --chain-path "${SSL_DIR}/live/${DOMAIN}/chain.pem"
    )
    
    if [ "${STAGING}" = "true" ] || [ "${STAGING}" = "--staging" ]; then
        certbot_args+=(--staging)
        warn "Using Let's Encrypt STAGING environment (not trusted by browsers)"
    fi
    
    # Create webroot for ACME challenges
    mkdir -p /var/www/certbot
    
    if certbot "${certbot_args[@]}" 2>&1 | tee -a "${LOG_FILE}"; then
        success "Certificate obtained successfully"
    else
        error "Failed to obtain certificate"
        exit 1
    fi
}

setup_auto_renewal() {
    info "Setting up automatic certificate renewal..."
    
    # Create renewal script
    mkdir -p "${ERP_DIR}/scripts"
    cat > "${ERP_DIR}/scripts/renew-ssl.sh" <<'RENEWAL_SCRIPT'
#!/bin/bash
# Auto-generated SSL renewal script

set -euo pipefail

LOG_FILE="${ERP_DIR}/logs/ssl-renewal-$(date +%Y%m%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

log "Starting SSL certificate renewal check..."

if certbot renew --nginx --quiet 2>&1 | tee -a "${LOG_FILE}"; then
    log "Certificate renewal check completed"
    
    # Reload nginx if certificates were renewed
    if grep -q "Renewed" /var/log/letsencrypt/letsencrypt.log 2>/dev/null; then
        log "Certificates renewed, reloading nginx..."
        docker exec erp-nginx nginx -s reload 2>&1 | tee -a "${LOG_FILE}"
        log "Nginx reloaded"
    fi
else
    log "ERROR: Certificate renewal failed"
    exit 1
fi
RENEWAL_SCRIPT
    
    chmod +x "${ERP_DIR}/scripts/renew-ssl.sh"
    
    # Add cron job for daily renewal check
    (crontab -l 2>/dev/null | grep -v "renew-ssl.sh"; echo "0 3 * * * ${ERP_DIR}/scripts/renew-ssl.sh") | crontab -
    
    success "Auto-renewal configured (daily at 3 AM)"
}

update_nginx_main_config() {
    info "Checking main nginx configuration..."
    
    # nginx.conf already carries "include /etc/nginx/conf.d/ssl.conf;" inside
    # its http block, so there is nothing to inject - just make sure it is
    # still there before we rely on the reload below.
    if grep -q "include /etc/nginx/conf.d/ssl.conf;" "${NGINX_CONF_FILE}" 2>/dev/null; then
        success "Main nginx.conf includes /etc/nginx/conf.d/ssl.conf"
    else
        error "Main nginx config ${NGINX_CONF_FILE} is missing"
        error "  'include /etc/nginx/conf.d/ssl.conf;' inside the http block"
        exit 1
    fi
}

reload_nginx() {
    info "Reloading nginx..."
    # Validates with `nginx -t` first. Without that check a typo in the
    # generated block would make the reload fail and, in some setups, leave the
    # proxy serving a stale or broken config.
    if ! docker info >/dev/null 2>&1; then
        warn "Docker daemon not running; cannot reload nginx."
        warn "Start it and run: docker exec erp-nginx nginx -s reload"
        return 1
    fi
    if ! erp_container_exists erp-nginx; then
        warn "erp-nginx is not running; cannot reload."
        return 1
    fi
    if ! docker exec erp-nginx nginx -t; then
        error "nginx configuration test failed; not reloading."
        error "Check ${NGINX_CONF_DIR}/ssl.conf and the certificate paths:"
        error "  ${SSL_DIR}/live/${DOMAIN}/fullchain.pem"
        return 1
    fi
    erp_reload_nginx erp-nginx || return 1
    success "Nginx reloaded successfully"
}

main() {
    info "=========================================="
    info "ERP SOLUTION — SSL Setup"
    info "Domain: ${DOMAIN}"
    info "Email: ${EMAIL}"
    info "Staging: ${STAGING}"
    info "Log file: ${LOG_FILE}"
    info "=========================================="
    
    mkdir -p "$(dirname "${LOG_FILE}")"
    
    validate_inputs
    generate_nginx_config
    obtain_certificate
    setup_auto_renewal
    update_nginx_main_config
    reload_nginx
    
    success "=========================================="
    success "SSL setup completed successfully!"
    success "Certificate: ${SSL_DIR}/live/${DOMAIN}/fullchain.pem"
    success "Private key: ${SSL_DIR}/live/${DOMAIN}/privkey.pem"
    success "Auto-renewal: configured (daily at 3 AM)"
    success "=========================================="
}

main "$@"