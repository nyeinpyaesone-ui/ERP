#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Blue-Green Deployment Script
# Usage: ./scripts/deploy-blue-green.sh [environment] [version] [--rollback]
# Works with docker-compose.prod.yml fixed container names and profiles
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
NGINX_UPSTREAM_DIR_HOST="${PROJECT_ROOT}/nginx"
NGINX_UPSTREAM_DIR_CONTAINER="/etc/nginx/conf.d"
SSL_DIR="/opt/erp-solution/ssl"
ERP_DIR="/opt/erp-solution"

ENVIRONMENT="${1:-production}"
VERSION="${2:-latest}"
ROLLBACK="${3:-false}"

ACTIVE_COLOR_FILE="/opt/erp-solution/.active_color"
PREVIOUS_VERSION_FILE="/opt/erp-solution/.previous_version"

LOG_FILE="/opt/erp-solution/logs/deploy-$(date +%Y%m%d-%H%M%S).log"

DOCKER_COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
else
    DOCKER_COMPOSE_CMD="docker-compose"
fi

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
        error "Deployment failed with exit code $exit_code"
        error "Check log: ${LOG_FILE}"
    fi
    exit $exit_code
}
trap cleanup EXIT

validate_environment() {
    info "Validating environment: ${ENVIRONMENT}"
    
    if [[ ! "${ENVIRONMENT}" =~ ^(staging|production)$ ]]; then
        error "Environment must be 'staging' or 'production'"
        exit 1
    fi
    
    if [ ! -f "${COMPOSE_FILE}" ]; then
        error "Compose file not found: ${COMPOSE_FILE}"
        exit 1
    fi
    
    if [ ! -d "${NGINX_UPSTREAM_DIR_HOST}" ]; then
        error "Nginx upstream directory not found: ${NGINX_UPSTREAM_DIR_HOST}"
        exit 1
    fi
    
    if [ -z "${DOCKER_COMPOSE_CMD}" ]; then
        error "docker-compose not available"
        exit 1
    fi
    
    success "Environment validation passed"
}

get_active_color() {
    if [ -f "${ACTIVE_COLOR_FILE}" ]; then
        cat "${ACTIVE_COLOR_FILE}"
    else
        echo "blue"
    fi
}

get_inactive_color() {
    local active=$(get_active_color)
    if [ "${active}" = "blue" ]; then
        echo "green"
    else
        echo "blue"
    fi
}

get_container_name() {
    local color="$1"
    local service="$2"
    echo "erp-${color}-${service}"
}

pull_images() {
    local color="$1"
    info "Pulling images for ${color} environment (version: ${VERSION})"
    
    # Pull blue images (always)
    $DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" pull backend frontend 2>&1 | tee -a "${LOG_FILE}"
    
    # Pull green images if using blue-green
    if [ "${color}" = "green" ]; then
        $DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" --profile blue-green pull backend-green frontend-green 2>&1 | tee -a "${LOG_FILE}"
    fi
    
    success "Images pulled successfully"
}

start_inactive_environment() {
    local color="$1"
    
    info "Starting ${color} environment"
    
    if [ "${color}" = "blue" ]; then
        # Blue is default profile - always running
        $DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" up -d backend frontend 2>&1 | tee -a "${LOG_FILE}"
    else
        # Green uses blue-green profile
        $DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" --profile blue-green up -d backend-green frontend-green 2>&1 | tee -a "${LOG_FILE}"
    fi
    
    success "${color} environment started"
}

wait_for_health() {
    local color="$1"
    local backend_container=$(get_container_name "${color}" "backend")
    local max_attempts=30
    local attempt=1
    
    info "Waiting for ${color} environment to become healthy..."
    
    while [ $attempt -le $max_attempts ]; do
        local health_status=$(docker inspect --format='{{.State.Health.Status}}' "${backend_container}" 2>/dev/null || echo "unknown")
        
        if [ "${health_status}" = "healthy" ]; then
            success "${color} environment is healthy"
            return 0
        fi
        
        if [ "${health_status}" = "unhealthy" ]; then
            error "${color} environment is unhealthy"
            docker logs "${backend_container}" --tail 50 | tee -a "${LOG_FILE}"
            return 1
        fi
        
        info "Attempt ${attempt}/${max_attempts}: ${color} health status = ${health_status}"
        sleep 10
        ((attempt++))
    done
    
    error "${color} environment did not become healthy within timeout"
    docker logs "${backend_container}" --tail 100 | tee -a "${LOG_FILE}"
    return 1
}

run_smoke_tests() {
    local color="$1"
    local backend_container=$(get_container_name "${color}" "backend")
    
    info "Running smoke tests against ${color} environment..."
    
    # Test health endpoint
    if ! docker exec "${backend_container}" curl -sf http://localhost:8000/health > /dev/null; then
        error "Health check failed"
        return 1
    fi
    
    # Test readiness endpoint
    if ! docker exec "${backend_container}" curl -sf http://localhost:8000/ready > /dev/null; then
        error "Readiness check failed"
        return 1
    fi
    
    # Test API root
    if ! docker exec "${backend_container}" curl -sf http://localhost:8000/ > /dev/null; then
        error "API root check failed"
        return 1
    fi
    
    success "Smoke tests passed for ${color} environment"
    return 0
}

switch_traffic() {
    local new_color="$1"
    local old_color="$2"
    
    info "Switching traffic from ${old_color} to ${new_color}"
    
    local new_upstream_host="${NGINX_UPSTREAM_DIR_HOST}/upstream-${new_color}.conf"
    local new_upstream_container="${NGINX_UPSTREAM_DIR_CONTAINER}/upstream-${new_color}.conf"
    local active_upstream_container="${NGINX_UPSTREAM_DIR_CONTAINER}/upstream-active.conf"
    
    if [ ! -f "${new_upstream_host}" ]; then
        error "Upstream config not found: ${new_upstream_host}"
        return 1
    fi
    
    # Atomic switch - create symlink inside nginx container
    if docker exec erp-nginx ln -sf "${new_upstream_container}" "${active_upstream_container}" 2>&1 | tee -a "${LOG_FILE}"; then
        info "Symlink created inside nginx container"
    else
        error "Failed to create symlink inside nginx container"
        return 1
    fi
    
    # Reload nginx
    if docker exec erp-nginx nginx -s reload 2>&1 | tee -a "${LOG_FILE}"; then
        success "Traffic switched to ${new_color}"
    else
        error "Failed to reload nginx"
        return 1
    fi
    
    # Update active color file on host
    echo "${new_color}" > "${ACTIVE_COLOR_FILE}"
    
    # Store previous version for rollback
    if [ -f "${PREVIOUS_VERSION_FILE}" ]; then
        mv "${PREVIOUS_VERSION_FILE}" "${PREVIOUS_VERSION_FILE}.bak"
    fi
    echo "${VERSION}" > "${PREVIOUS_VERSION_FILE}"
}

stop_old_environment() {
    local color="$1"
    
    info "Stopping old ${color} environment"
    
    if [ "${color}" = "blue" ]; then
        # Blue is default - just stop services
        $DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" stop backend frontend 2>&1 | tee -a "${LOG_FILE}"
    else
        # Green uses blue-green profile
        $DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" --profile blue-green stop backend-green frontend-green 2>&1 | tee -a "${LOG_FILE}"
    fi
    
    success "Old ${color} environment stopped"
}

perform_rollback() {
    info "Performing rollback..."
    
    local current_color=$(get_active_color)
    local previous_color=$(get_inactive_color)
    local previous_version=""
    
    if [ -f "${PREVIOUS_VERSION_FILE}" ]; then
        previous_version=$(cat "${PREVIOUS_VERSION_FILE}")
    else
        error "No previous version recorded for rollback"
        return 1
    fi
    
    warn "Rolling back from ${current_color} to ${previous_color} (version: ${previous_version})"
    
    # Switch traffic back
    switch_traffic "${previous_color}" "${current_color}"
    
    # Stop the failed environment
    stop_old_environment "${current_color}"
    
    success "Rollback completed to ${previous_color} (version: ${previous_version})"
}

load_env() {
    local env_file="${ERP_DIR}/.env.production"
    if [ -f "${env_file}" ]; then
        info "Loading environment from ${env_file}"
        set -a
        source "${env_file}"
        set +a
    else
        warn "Environment file not found: ${env_file}"
    fi
}

main() {
    info "=========================================="
    info "ERP SOLUTION — Blue-Green Deployment"
    info "Environment: ${ENVIRONMENT}"
    info "Version: ${VERSION}"
    info "Rollback mode: ${ROLLBACK}"
    info "Log file: ${LOG_FILE}"
    info "=========================================="
    
    mkdir -p "$(dirname "${LOG_FILE}")"
    
    load_env
    validate_environment
    
    if [ "${ROLLBACK}" = "true" ] || [ "${ROLLBACK}" = "--rollback" ]; then
        perform_rollback
        exit 0
    fi
    
    local active_color=$(get_active_color)
    local inactive_color=$(get_inactive_color)
    
    info "Active color: ${active_color}"
    info "Inactive color: ${inactive_color}"
    
    # Pull images for inactive environment
    pull_images "${inactive_color}"
    
    # Start inactive environment
    start_inactive_environment "${inactive_color}"
    
    # Wait for health
    if ! wait_for_health "${inactive_color}"; then
        error "Inactive environment failed health checks"
        if [ "${inactive_color}" = "green" ]; then
            $DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" --profile blue-green stop backend-green frontend-green
        fi
        exit 1
    fi
    
    # Run smoke tests
    if ! run_smoke_tests "${inactive_color}"; then
        error "Smoke tests failed"
        if [ "${inactive_color}" = "green" ]; then
            $DOCKER_COMPOSE_CMD -f "${COMPOSE_FILE}" --profile blue-green stop backend-green frontend-green
        fi
        exit 1
    fi
    
    # Switch traffic
    if ! switch_traffic "${inactive_color}" "${active_color}"; then
        error "Traffic switch failed"
        exit 1
    fi
    
    # Verify traffic switch with external check
    sleep 5
    if ! run_smoke_tests "${inactive_color}"; then
        error "Post-switch smoke tests failed, rolling back..."
        switch_traffic "${active_color}" "${inactive_color}"
        stop_old_environment "${inactive_color}"
        exit 1
    fi
    
    # Stop old environment
    stop_old_environment "${active_color}"
    
    success "=========================================="
    success "Deployment completed successfully!"
    success "Active environment: ${inactive_color}"
    success "Version: ${VERSION}"
    success "=========================================="
}

main "$@"