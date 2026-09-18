#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — End-User Production Installation Script
# Usage: sudo ./install.sh [domain] [email]
# Example: sudo ./install.sh erp.example.com admin@example.com
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}"

DOMAIN="${1:-}"
EMAIL="${2:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERP_DIR="/opt/erp-solution"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
NGINX_DIR="${PROJECT_ROOT}/nginx"
SSL_DIR="${ERP_DIR}/ssl"
LOG_DIR="${ERP_DIR}/logs"
BACKUP_DIR="${ERP_DIR}/backups"

log() {
    local level="$1"; shift
    local msg="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${msg}"
}
info() { log "INFO" "${BLUE}$*${NC}"; }
success() { log "SUCCESS" "${GREEN}$*${NC}"; }
warn() { log "WARN" "${YELLOW}$*${NC}"; }
error() { log "ERROR" "${RED}$*${NC}"; }

usage() {
    cat <<EOF
ERP Solution Production Installer

Usage: sudo ./install.sh [DOMAIN] [EMAIL]

Arguments:
  DOMAIN    Your domain name (e.g., erp.example.com)
  EMAIL     Email for Let's Encrypt SSL certificates

Examples:
  sudo ./install.sh erp.example.com admin@example.com
  sudo ./install.sh                          # Interactive mode

This script will:
  1. Install Docker, Docker Compose, Certbot
  2. Create directory structure at /opt/erp-solution
  3. Generate production .env file
  4. Obtain SSL certificates via Let's Encrypt
  5. Configure Nginx with your domain
  6. Deploy using blue-green strategy
  7. Run database migrations

EOF
}

prompt_input() {
    local prompt="$1"
    local var_name="$2"
    local default="${3:-}"
    local value
    
    if [ -n "$default" ]; then
        read -rp "$prompt [$default]: " value
        value="${value:-$default}"
    else
        read -rp "$prompt: " value
        while [ -z "$value" ]; do
            read -rp "$prompt (required): " value
        done
    fi
    eval "$var_name='$value'"
}

generate_random_secret() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "This script must be run as root (use sudo)"
        exit 1
    fi
}

install_dependencies() {
    info "Installing system dependencies..."
    apt-get update -qq
    apt-get install -y -qq curl gnupg2 lsb-release ca-certificates \
        software-properties-common certbot python3-certbot-nginx > /dev/null
    
    if ! command -v docker &> /dev/null; then
        info "Installing Docker..."
        curl -fsSL https://get.docker.com | sh > /dev/null
    fi
    
    DOCKER_COMPOSE_CMD=""
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
    elif command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        info "Installing Docker Compose..."
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
            -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        DOCKER_COMPOSE_CMD="docker-compose"
    fi
    export DOCKER_COMPOSE_CMD
    
    success "Dependencies installed"
}

create_directories() {
    info "Creating directory structure..."
    mkdir -p "${ERP_DIR}"/{ssl,logs/nginx,backups,uploads}
    mkdir -p "${LOG_DIR}"
    chown -R "$SUDO_USER:$SUDO_USER" "${ERP_DIR}" 2>/dev/null || true
    success "Directories created at ${ERP_DIR}"
}

create_docker_network() {
    if ! docker network ls --format '{{.Name}}' | grep -q "^erp-network$"; then
        info "Creating Docker network..."
        docker network create erp-network
        success "Docker network created"
    else
        info "Docker network already exists"
    fi
}

generate_env_file() {
    info "Generating production environment file..."
    
    local db_password=$(generate_random_secret)
    local redis_password=$(generate_random_secret)
    local secret_key=$(generate_random_secret)
    local api_domain="api.${DOMAIN}"
    local app_domain="app.${DOMAIN}"
    
    cat > "${ERP_DIR}/.env.production" <<EOF
# ERP Solution Production Environment
# Generated on $(date)

# Database
DB_USER=erp
DB_PASSWORD=${db_password}
DB_NAME=erp_solution

# Redis
REDIS_PASSWORD=${redis_password}

# Security
SECRET_KEY=${secret_key}
ENVIRONMENT=production

# Domain Configuration
API_URL=https://${api_domain}
WS_URL=wss://${api_domain}
CORS_ORIGINS=https://${app_domain}

# Ollama
OLLAMA_URL=http://ollama:11434

# Docker
DOCKER_USER=powerrangeranikg
VERSION=latest

# Optional: Add your keys here
# STRIPE_SECRET_KEY=
# STRIPE_WEBHOOK_SECRET=
EOF
    
    chmod 600 "${ERP_DIR}/.env.production"
    chown "$SUDO_USER:$SUDO_USER" "${ERP_DIR}/.env.production" 2>/dev/null || true
    
    success "Environment file created at ${ERP_DIR}/.env.production"
    warn "IMPORTANT: Save these credentials securely:"
    warn "  DB_PASSWORD=${db_password}"
    warn "  REDIS_PASSWORD=${redis_password}"
    warn "  SECRET_KEY=${secret_key}"
}

configure_nginx() {
    info "Configuring Nginx for domain: ${DOMAIN}"
    
    local api_domain="api.${DOMAIN}"
    local app_domain="app.${DOMAIN}"
    
    sed -i "s/api.yourdomain.com/${api_domain}/g" "${NGINX_DIR}/upstream-blue.conf"
    sed -i "s/api.yourdomain.com/${api_domain}/g" "${NGINX_DIR}/upstream-green.conf"
    sed -i "s/app.yourdomain.com/${app_domain}/g" "${PROJECT_ROOT}/nginx.conf"
    sed -i "s/api.yourdomain.com/${api_domain}/g" "${PROJECT_ROOT}/nginx.conf"
    
    success "Nginx configuration updated"
}

obtain_ssl_certificates() {
    info "Obtaining SSL certificates from Let's Encrypt..."
    
    local api_domain="api.${DOMAIN}"
    local app_domain="app.${DOMAIN}"
    
    systemctl stop nginx 2>/dev/null || true
    
    certbot certonly --standalone --non-interactive --agree-tos \
        --email "${EMAIL}" \
        -d "${api_domain}" -d "${app_domain}" \
        --expand 2>&1 | tail -20
    
    if [ -f "/etc/letsencrypt/live/${api_domain}/fullchain.pem" ]; then
        cp "/etc/letsencrypt/live/${api_domain}/fullchain.pem" "${SSL_DIR}/cert.pem"
        cp "/etc/letsencrypt/live/${api_domain}/privkey.pem" "${SSL_DIR}/key.pem"
        chown "$SUDO_USER:$SUDO_USER" "${SSL_DIR}"/*.pem 2>/dev/null || true
        success "SSL certificates obtained and copied"
    else
        error "Failed to obtain SSL certificates"
        warn "You can manually run: certbot --nginx -d ${api_domain} -d ${app_domain}"
        return 1
    fi
}

setup_certbot_renewal() {
    info "Setting up automatic certificate renewal..."
    
    cat > /etc/cron.d/erp-certbot-renewal <<EOF
# Renew Let's Encrypt certificates for ERP Solution
0 3 * * * root certbot renew --quiet --post-hook "cp /etc/letsencrypt/live/api.${DOMAIN}/fullchain.pem ${SSL_DIR}/cert.pem && cp /etc/letsencrypt/live/api.${DOMAIN}/privkey.pem ${SSL_DIR}/key.pem && docker exec erp-nginx nginx -s reload"
EOF
    
    success "Auto-renewal configured"
}

deploy_initial() {
    info "Starting initial deployment (blue environment)..."
    
    cd "${PROJECT_ROOT}"
    
    export $(grep -v '^#' "${ERP_DIR}/.env.production" | xargs)
    
    $DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" pull postgres redis ollama 2>&1 | tail -10
    
    $DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" up -d postgres redis ollama 2>&1 | tail -5
    
    info "Waiting for database to be ready..."
    local attempt=1
    while [ $attempt -le 30 ]; do
        if docker exec erp-postgres pg_isready -U erp > /dev/null 2>&1; then
            success "Database is ready"
            break
        fi
        sleep 2
        ((attempt++))
    done
    
    if [ $attempt -gt 30 ]; then
        error "Database failed to start"
        return 1
    fi
    
    info "Running database migrations..."
    $DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" run --rm backend alembic upgrade head 2>&1 | tail -20
    
    info "Starting blue environment..."
    $DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" up -d backend frontend nginx 2>&1 | tail -10
    
    info "Waiting for services to be healthy..."
    sleep 15
    
    local backend_healthy=false
    for i in {1..20}; do
        if docker exec erp-blue-backend curl -sf http://localhost:8000/ready > /dev/null 2>&1; then
            backend_healthy=true
            break
        fi
        sleep 5
    done
    
    if [ "$backend_healthy" = true ]; then
        success "Blue environment deployed successfully"
    else
        error "Backend health check failed"
        docker logs erp-blue-backend --tail 50
        return 1
    fi
}

verify_deployment() {
    info "Verifying deployment..."
    
    local api_domain="api.${DOMAIN}"
    local app_domain="app.${DOMAIN}"
    
    if curl -sf "https://${api_domain}/health" > /dev/null; then
        success "API health check passed"
    else
        warn "API health check failed (may need DNS propagation)"
    fi
    
    if curl -sf "https://${app_domain}" > /dev/null; then
        success "Frontend health check passed"
    else
        warn "Frontend health check failed (may need DNS propagation)"
    fi
}

print_summary() {
    local api_domain="api.${DOMAIN}"
    local app_domain="app.${DOMAIN}"
    
    cat <<EOF

==========================================
  ERP SOLUTION — Installation Complete!
==========================================

Domain Configuration:
  API:  https://${api_domain}
  App:  https://${app_domain}

Credentials (saved in ${ERP_DIR}/.env.production):
  Database: postgresql://erp:<DB_PASSWORD>@localhost:5432/erp_solution
  Redis:    redis://:<REDIS_PASSWORD>@localhost:6379/0

Next Steps:
  1. Configure DNS A records for ${api_domain} and ${app_domain} -> this server IP
  2. Test the application at https://${app_domain}
  3. Default login: admin / changeme123 (CHANGE IMMEDIATELY)

Management Commands:
  Deploy update:     ./scripts/deploy-blue-green.sh production v1.2.3
  Rollback:          ./scripts/deploy-blue-green.sh production v1.2.3 --rollback
  View logs:         ${DOCKER_COMPOSE_CMD} -f ${COMPOSE_FILE} logs -f
  Backup database:   ./scripts/backup.sh
  Scale services:    ${DOCKER_COMPOSE_CMD} -f ${COMPOSE_FILE} up -d --scale backend=2

Important Files:
  Environment: ${ERP_DIR}/.env.production
  SSL Certs:   ${SSL_DIR}/
  Logs:        ${LOG_DIR}/
  Backups:     ${BACKUP_DIR}/

EOF
}

main() {
    echo -e "${BLUE}"
    cat <<'BANNER'
  _____       _ _     _   _ _     
 |  __ \     | | |   | \ | | |    
 | |  | | ___| | |__ |  \| | |___ 
 | |  | |/ _ \ | '_ \| . ` | / __|
 | |__| |  __/ | |_) | |\  | \__ \
 |_____/ \___|_|_.__/|_| \_|_|___/
                                 
BANNER
    echo -e "${NC}"
    
    check_root
    
    if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
        usage
        prompt_input "Enter your domain (e.g., erp.example.com)" DOMAIN
        prompt_input "Enter email for SSL certificates" EMAIL
    fi
    
    info "Starting ERP Solution installation for ${DOMAIN}"
    
    install_dependencies
    create_directories
    create_docker_network
    generate_env_file
    configure_nginx
    
    if obtain_ssl_certificates; then
        setup_certbot_renewal
    fi
    
    deploy_initial
    verify_deployment
    print_summary
    
    success "Installation completed successfully!"
}

main "$@"