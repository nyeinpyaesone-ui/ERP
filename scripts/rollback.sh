#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Rollback Script
# Usage: ./scripts/rollback.sh [environment] [version]
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NGINX_UPSTREAM_DIR="/etc/nginx/conf.d"
ACTIVE_COLOR_FILE="/opt/erp-solution/.active_color"
PREVIOUS_VERSION_FILE="/opt/erp-solution/.previous_version"
LOG_FILE="/opt/erp-solution/logs/rollback-$(date +%Y%m%d-%H%M%S).log"

ENVIRONMENT="${1:-production}"
TARGET_VERSION="${2:-}"

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

validate_environment() {
    info "Validating environment: ${ENVIRONMENT}"
    
    if [[ ! "${ENVIRONMENT}" =~ ^(staging|production)$ ]]; then
        error "Environment must be 'staging' or 'production'"
        exit 1
    fi
    
    if [ ! -f "${ACTIVE_COLOR_FILE}" ]; then
        error "No active deployment found (${ACTIVE_COLOR_FILE} missing)"
        exit 1
    fi
    
    success "Environment validation passed"
}

get_active_color() {
    cat "${ACTIVE_COLOR_FILE}"
}

get_inactive_color() {
    local active=$(get_active_color)
    if [ "${active}" = "blue" ]; then
        echo "green"
    else
        echo "blue"
    fi
}

get_project_name() {
    local color="$1"
    echo "${ENVIRONMENT}-${color}"
}

perform_rollback() {
    local current_color=$(get_active_color)
    local previous_color=$(get_inactive_color)
    local current_project=$(get_project_name "${current_color}")
    local previous_project=$(get_project_name "${previous_color}")
    
    info "Current active: ${current_color} (${current_project})"
    info "Rolling back to: ${previous_color} (${previous_project})"
    
    # Determine target version
    local rollback_version=""
    if [ -n "${TARGET_VERSION}" ]; then
        rollback_version="${TARGET_VERSION}"
        info "Using specified version: ${rollback_version}"
    elif [ -f "${PREVIOUS_VERSION_FILE}" ]; then
        rollback_version=$(cat "${PREVIOUS_VERSION_FILE}")
        info "Using previous version: ${rollback_version}"
    else
        error "No previous version recorded and no target version specified"
        exit 1
    fi
    
    # Pull the rollback version if needed
    info "Ensuring rollback version images are available..."
    docker-compose -p "${previous_project}" -f "${PROJECT_ROOT}/docker-compose.prod.yml" pull backend frontend 2>&1 | tee -a "${LOG_FILE}"
    
    # Start the previous environment if not running
    info "Starting ${previous_color} environment..."
    docker-compose -p "${previous_project}" -f "${PROJECT_ROOT}/docker-compose.prod.yml" up -d backend frontend 2>&1 | tee -a "${LOG_FILE}"
    
    # Wait for health
    local max_attempts=30
    local attempt=1
    
    info "Waiting for ${previous_color} environment to become healthy..."
    while [ $attempt -le $max_attempts ]; do
        local health_status=$(docker inspect --format='{{.State.Health.Status}}' "${previous_project}-backend-1" 2>/dev/null || echo "unknown")
        
        if [ "${health_status}" = "healthy" ]; then
            success "${previous_color} environment is healthy"
            break
        fi
        
        if [ "${health_status}" = "unhealthy" ]; then
            error "${previous_color} environment is unhealthy"
            docker logs "${previous_project}-backend-1" --tail 50 | tee -a "${LOG_FILE}"
            exit 1
        fi
        
        info "Attempt ${attempt}/${max_attempts}: ${previous_color} health status = ${health_status}"
        sleep 10
        ((attempt++))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        error "${previous_color} environment did not become healthy within timeout"
        exit 1
    fi
    
    # Run smoke tests
    info "Running smoke tests against ${previous_color} environment..."
    local backend_container="${previous_project}-backend-1"
    
    if ! docker exec "${backend_container}" curl -sf http://localhost:8000/health > /dev/null; then
        error "Health check failed"
        exit 1
    fi
    
    if ! docker exec "${backend_container}" curl -sf http://localhost:8000/ready > /dev/null; then
        error "Readiness check failed"
        exit 1
    fi
    
    success "Smoke tests passed"
    
    # Switch traffic
    info "Switching traffic back to ${previous_color}..."
    local previous_upstream="${NGINX_UPSTREAM_DIR}/upstream-${previous_color}.conf"
    local active_upstream="${NGINX_UPSTREAM_DIR}/upstream-active.conf"
    
    if [ ! -f "${previous_upstream}" ]; then
        error "Upstream config not found: ${previous_upstream}"
        exit 1
    fi
    
    ln -sf "${previous_upstream}" "${active_upstream}"
    
    if docker exec erp-nginx nginx -s reload 2>&1 | tee -a "${LOG_FILE}"; then
        success "Traffic switched to ${previous_color}"
    else
        error "Failed to reload nginx"
        exit 1
    fi
    
    # Update active color file
    echo "${previous_color}" > "${ACTIVE_COLOR_FILE}"
    
    # Update version file
    echo "${rollback_version}" > "${PREVIOUS_VERSION_FILE}"
    
    # Stop the failed environment
    info "Stopping failed ${current_color} environment..."
    docker-compose -p "${current_project}" -f "${PROJECT_ROOT}/docker-compose.prod.yml" down backend frontend 2>&1 | tee -a "${LOG_FILE}"
    
    success "=========================================="
    success "Rollback completed successfully!"
    success "Active environment: ${previous_color} (${previous_project})"
    success "Version: ${rollback_version}"
    success "=========================================="
}

main() {
    info "=========================================="
    info "ERP SOLUTION — Rollback"
    info "Environment: ${ENVIRONMENT}"
    info "Target version: ${TARGET_VERSION:-auto}"
    info "Log file: ${LOG_FILE}"
    info "=========================================="
    
    mkdir -p "$(dirname "${LOG_FILE}")"
    
    validate_environment
    perform_rollback
}

main "$@"