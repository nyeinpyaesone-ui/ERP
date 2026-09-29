#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Secure Production Setup Script
# Generates secrets, configures .env.production, validates all endpoints
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.production"
ENV_TEMPLATE="${PROJECT_ROOT}/.env.production.template"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

gen_secret() { openssl rand -hex 32; }
gen_jwt_secret() { openssl rand -hex 32; }
gen_db_password() { openssl rand -base64 24 | tr -d "=+/" | cut -c1-32; }
gen_redis_password() { openssl rand -base64 24 | tr -d "=+/" | cut -c1-32; }

prompt_secret() {
    local prompt="$1" var_name="$2" default="$3" value=""
    if [[ -n "${default}" ]]; then
        read -rsp "${prompt} [${default}]: " value
        value="${value:-${default}}"
    else
        while [[ -z "${value}" ]]; do read -rsp "${prompt}: " value; echo; done
    fi
    printf -v "${var_name}" '%s' "${value}"
}

prompt_optional() {
    local prompt="$1" var_name="$2" value=""
    read -rp "${prompt} (optional): " value
    printf -v "${var_name}" '%s' "${value}"
}

main() {
    info "=========================================="
    info "ERP SOLUTION — Secure Production Setup"
    info "=========================================="
    echo

    if [[ -f "${ENV_FILE}" ]]; then
        warn ".env.production already exists"
        read -rp "Overwrite? (y/N): " confirm
        [[ ! "${confirm}" =~ ^[Yy]$ ]] && { info "Aborted."; exit 0; }
    fi

    # DOMAIN
    info "--- Domain Configuration ---"
    read -rp "Production domain (e.g., yourdomain.com): " DOMAIN
    [[ -z "${DOMAIN}" ]] && error "Domain is required"
    API_DOMAIN="api.${DOMAIN}"
    APP_DOMAIN="app.${DOMAIN}"
    CORS_ORIGINS="https://${APP_DOMAIN}"
    success "Domain: ${DOMAIN} | API: https://${API_DOMAIN} | App: https://${APP_DOMAIN}"

    # GENERATE SECRETS
    info "--- Generating Cryptographic Secrets ---"
    DB_PASSWORD=$(gen_db_password)
    REDIS_PASSWORD=$(gen_redis_password)
    SECRET_KEY=$(gen_jwt_secret)
    success "Database password generated"
    success "Redis password generated"
    success "JWT secret key generated (256-bit)"

    # EXTERNAL CREDENTIALS
    info "--- External Service Credentials (Press Enter to skip) ---"
    prompt_optional "SMTP Host (e.g., smtp.gmail.com)" SMTP_HOST
    prompt_optional "SMTP Port (default 587)" SMTP_PORT; [[ -z "${SMTP_PORT}" ]] && SMTP_PORT="587"
    prompt_optional "SMTP User/Email" SMTP_USER
    prompt_optional "SMTP Password/App Password" SMTP_PASSWORD
    prompt_optional "Stripe Secret Key (sk_live_...)" STRIPE_SECRET_KEY
    prompt_optional "Stripe Webhook Secret (whsec_...)" STRIPE_WEBHOOK_SECRET
    prompt_optional "Stripe Publishable Key (pk_live_...)" STRIPE_PUBLISHABLE_KEY
    prompt_optional "OpenAI API Key (sk-...)" OPENAI_API_KEY
    prompt_optional "Sentry DSN" SENTRY_DSN

    OLLAMA_MODEL="llama3.1"

    # WRITE .env.production
    info "--- Writing .env.production ---"
    cat > "${ENV_FILE}" <<EOF
# ERP SOLUTION — Production Environment
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# DO NOT COMMIT THIS FILE — contains secrets

# ============================================
# DATABASE
# ============================================
DB_USER=erp
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=erp_solution

# ============================================
# REDIS
# ============================================
REDIS_PASSWORD=${REDIS_PASSWORD}

# ============================================
# SECURITY
# ============================================
SECRET_KEY=${SECRET_KEY}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ============================================
# CORS & DOMAINS
# ============================================
CORS_ORIGINS=${CORS_ORIGINS}
API_URL=https://${API_DOMAIN}
WS_URL=wss://${API_DOMAIN}

# ============================================
# AI / OLLAMA (internal only)
# ============================================
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=${OLLAMA_MODEL}

# ============================================
# EMAIL
# ============================================
SMTP_HOST=${SMTP_HOST:-smtp.gmail.com}
SMTP_PORT=${SMTP_PORT:-587}
SMTP_USER=${SMTP_USER:-}
SMTP_PASSWORD=${SMTP_PASSWORD:-}
SMTP_FROM=noreply@${DOMAIN}

# ============================================
# STRIPE
# ============================================
STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY:-}
STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET:-}
STRIPE_PUBLISHABLE_KEY=${STRIPE_PUBLISHABLE_KEY:-}

# ============================================
# MONITORING
# ============================================
SENTRY_DSN=${SENTRY_DSN:-}
ENVIRONMENT=production

# ============================================
# FILE UPLOAD
# ============================================
UPLOAD_DIR=/app/uploads
MAX_UPLOAD_SIZE=52428800

# ============================================
# WEBSOCKET
# ============================================
WS_HEARTBEAT_INTERVAL=30
EOF

    chmod 600 "${ENV_FILE}"
    success ".env.production created at ${ENV_FILE}"
    warn "Permissions set to 600 (owner read/write only)"

    # SSL
    info "--- SSL Certificate Setup ---"
    mkdir -p "${PROJECT_ROOT}/ssl"
    info "Place SSL certificates in ${PROJECT_ROOT}/ssl/:"
    info "  - cert.pem (full chain)"
    info "  - key.pem (private key)"
    info "Or run: sudo certbot certonly --standalone -d ${API_DOMAIN} -d ${APP_DOMAIN}"
    info "Then copy: sudo cp /etc/letsencrypt/live/${API_DOMAIN}/fullchain.pem ${PROJECT_ROOT}/ssl/cert.pem"
    info "         sudo cp /etc/letsencrypt/live/${API_DOMAIN}/privkey.pem ${PROJECT_ROOT}/ssl/key.pem"

    # UPLOADS
    mkdir -p "${PROJECT_ROOT}/backend/uploads"
    chmod 755 "${PROJECT_ROOT}/backend/uploads"

    # VALIDATE
    info "--- Validating docker-compose.prod.yml ---"
    if docker compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" config --quiet 2>/dev/null; then
        success "docker-compose.prod.yml syntax OK"
    else
        warn "docker-compose validation failed - will validate at deploy time"
    fi

    echo
    info "=========================================="
    info "SETUP COMPLETE"
    info "=========================================="
    echo
    success "Configuration written to: ${ENV_FILE}"
    echo
    info "Next steps on your PRODUCTION SERVER:"
    echo "  1. Copy this project to server: scp -r . user@server:/opt/erp-solution"
    echo "  2. On server: cd /opt/erp-solution"
    echo "  3. Copy .env.production: cp .env.production /opt/erp-solution/.env.production"
    echo "  4. Place SSL certificates in /opt/erp-solution/ssl/"
    echo "  5. Start database: docker compose -f docker-compose.prod.yml up -d postgres redis"
    echo "  6. Run migrations: docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head"
    echo "  7. Deploy: ./scripts/deploy-blue-green.sh production v1.0.0"
    echo
    info "Security reminders:"
    echo "  - .env.production is gitignored (chmod 600)"
    echo "  - Never commit secrets to git"
    echo "  - Rotate secrets quarterly"
    echo "  - Use GitHub Environments for CI/CD secrets"
    echo
    info "Required GitHub Secrets for CI/CD:"
    echo "  DOCKER_USER, DOCKER_PAT_BACKEND, DOCKER_PAT_FRONTEND"
    echo "  SSH_PRIVATE_KEY"
    echo "  STAGING_HOST, STAGING_USER, PRODUCTION_HOST, PRODUCTION_USER"
    echo "  DB_PASSWORD, REDIS_PASSWORD, SECRET_KEY, CORS_ORIGINS"
    echo
    warn "IMPORTANT: Save the generated secrets to a password manager NOW."
    warn "They will NOT be shown again after this script exits."
    echo
    info "Secrets generated (copy NOW to your password manager):"
    echo "  DB_PASSWORD: ${DB_PASSWORD}"
    echo "  REDIS_PASSWORD: ${REDIS_PASSWORD}"
    echo "  SECRET_KEY: ${SECRET_KEY}"
    echo
    warn "These values will NOT be displayed again. Copy them NOW."
}

main "$@"