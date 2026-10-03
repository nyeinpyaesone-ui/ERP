#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Automated SSL Setup with Let's Encrypt
# Usage: ./scripts/setup-ssl.sh [domain] [email] [--staging]
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NGINX_CONF_DIR="${PROJECT_ROOT}/nginx"
NGINX_CONF_FILE="${PROJECT_ROOT}/nginx.conf"
SSL_DIR="/opt/erp-solution/ssl"
# Path the same files have inside the erp-nginx container
# (docker-compose.prod.yml mounts <project>/ssl at /etc/nginx/ssl).
SSL_DIR_IN_CONTAINER="/etc/nginx/ssl"
LOG_FILE="/opt/erp-solution/logs/ssl-setup-$(date +%Y%m%d-%H%M%S).log"

DOMAIN="${1:-api.yourdomain.com}"
EMAIL="${2:-admin@yourdomain.com}"
STAGING="${3:-false}"

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
    echo -e "${timestamp} [${level}] ${msg}" | tee -a "${LOG_FILE}"
}

info() { log "INFO" "${BLUE}$*${NC}"; }
success() { log "SUCCESS" "${GREEN}$*${NC}"; }
warn() { log "WARN" "${YELLOW}$*${NC}"; }
error() { log "ERROR" "${RED}$*${NC}"; }

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
    info "Generating nginx configuration for ${DOMAIN}..."
    
    # Written over the placeholder nginx/ssl.conf that docker-compose.prod.yml
    # bind-mounts at /etc/nginx/conf.d/ssl.conf; nginx.conf includes that path
    # from its http block.  Certificate paths must be the in-container ones,
    # not the host paths.
    cat > "${NGINX_CONF_DIR}/ssl.conf" <<EOF
# Auto-generated SSL config for ${DOMAIN}
# DO NOT EDIT MANUALLY - managed by setup-ssl.sh

server {
    listen 80;
    server_name ${DOMAIN};
    
    # ACME challenge location for Let's Encrypt
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
        try_files \$uri =404;
    }
    
    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    http2 on;
    server_name ${DOMAIN};
    
    ssl_certificate ${SSL_DIR_IN_CONTAINER}/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key ${SSL_DIR_IN_CONTAINER}/live/${DOMAIN}/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' wss:;" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Rate limit for auth endpoints (zone declared in nginx.conf)
    location ~ ^/api/v1/auth/(login|register) {
        limit_req zone=auth_limit burst=3 nodelay;
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # API endpoints, including the WebSocket at /api/v1/ws
    location /api {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        # \$connection_upgrade is the map defined in nginx.conf; forcing
        # "upgrade" unconditionally breaks ordinary HTTP/1.1 requests.
        proxy_set_header Connection \$connection_upgrade;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
    }
    
    # Health/readiness checks (also reachable as /api/v1/health and
    # /api/v1/ready).  There is no /ws route - the WebSocket lives under /api.
    location /health {
        proxy_pass http://backend;
        access_log off;
    }
    
    location /ready {
        proxy_pass http://backend;
        access_log off;
    }
    
    # Everything else is the SPA
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
    
    success "Nginx config generated: ${NGINX_CONF_DIR}/ssl.conf"
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
    cat > "/opt/erp-solution/scripts/renew-ssl.sh" <<'RENEWAL_SCRIPT'
#!/bin/bash
# Auto-generated SSL renewal script

set -euo pipefail

LOG_FILE="/opt/erp-solution/logs/ssl-renewal-$(date +%Y%m%d).log"

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
    
    chmod +x "/opt/erp-solution/scripts/renew-ssl.sh"
    
    # Add cron job for daily renewal check
    (crontab -l 2>/dev/null | grep -v "renew-ssl.sh"; echo "0 3 * * * /opt/erp-solution/scripts/renew-ssl.sh") | crontab -
    
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
    
    if docker exec erp-nginx nginx -t 2>&1 | tee -a "${LOG_FILE}"; then
        docker exec erp-nginx nginx -s reload 2>&1 | tee -a "${LOG_FILE}"
        success "Nginx reloaded successfully"
    else
        error "Nginx configuration test failed"
        exit 1
    fi
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