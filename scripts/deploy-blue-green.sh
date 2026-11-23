#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Blue-Green Deployment Script
# Usage: ./scripts/deploy-blue-green.sh [environment] [version] [--rollback]
# Works with docker-compose.prod.yml fixed container names and profiles
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${SCRIPT_DIR}/lib.sh"
PROJECT_ROOT="${ERP_PROJECT_ROOT}"
COMPOSE_FILE="${ERP_COMPOSE_FILE}"
NGINX_UPSTREAM_DIR_HOST="${ERP_NGINX_DIR}"
NGINX_UPSTREAM_DIR_CONTAINER="/etc/nginx/conf.d"
SSL_DIR="${ERP_SSL_DIR}"
# State files live beside the env file, so an install outside /opt/erp-solution
# keeps its own blue/green bookkeeping instead of reading another tree's.
ACTIVE_COLOR_FILE="${ERP_DIR}/.active_color"
PREVIOUS_VERSION_FILE="${ERP_DIR}/.previous_version"
PREVIOUS_IMAGE_FILE="${ERP_DIR}/.previous_image"

# CLI arguments, captured before load_env runs. .env.production also defines
# ENVIRONMENT for the backend (dev|test|prod), so exporting it would overwrite
# the deploy target and validate_environment would reject "prod".
DEPLOY_TARGET_ENVIRONMENT="${1:-production}"
DEPLOY_TARGET_VERSION="${2:-latest}"
ROLLBACK="${3:-false}"

mkdir -p "${ERP_DIR}/logs"
LOG_FILE="${ERP_DIR}/logs/deploy-$(date +%Y%m%d-%H%M%S).log"

# compose detection lives in lib.sh; export the result under the historical name
# so the $DOCKER_COMPOSE_CMD call sites below are unchanged.
erp_detect_compose || { echo "docker compose not available" >&2; exit 1; }
DOCKER_COMPOSE_CMD="${ERP_COMPOSE_CMD}"

# Export VERSION so docker-compose can interpolate it
export VERSION

# Log through lib.sh so this script and install.sh write identically formatted
# records into the same log directory.
log()       { erp_log "$@"; }
info()      { erp_info "$@"; }
success()   { erp_success "$@"; }
warn()      { erp_warn "$@"; }
error()     { erp_error "$@"; }

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

    # Every compose call below interpolates ${DB_PASSWORD}, ${SECRET_KEY} and
    # ${VERSION} from this file. Without it compose substitutes blanks, and the
    # backend then fails closed at boot with an opaque error.
    if [ -z "${ERP_ENV_FILE:-}" ] || [ ! -f "${ERP_ENV_FILE}" ]; then
        error "Environment file not resolved; refusing to deploy with blank secrets."
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        error "Docker daemon is not reachable. Start it and retry."
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
    ${ERP_COMPOSE_CMD} --env-file "${ERP_ENV_FILE}" -f "${ERP_COMPOSE_FILE}" pull backend frontend 2>&1 | tee -a "${LOG_FILE}"
    
    # Pull green images if using blue-green
    if [ "${color}" = "green" ]; then
        ${ERP_COMPOSE_CMD} --env-file "${ERP_ENV_FILE}" -f "${ERP_COMPOSE_FILE}" --profile blue-green pull backend-green frontend-green 2>&1 | tee -a "${LOG_FILE}"
    fi
    
    success "Images pulled successfully"
}

start_inactive_environment() {
    local color="$1"
    
    info "Starting ${color} environment"
    
    if [ "${color}" = "blue" ]; then
        # Blue is default profile - always running
        ${ERP_COMPOSE_CMD} --env-file "${ERP_ENV_FILE}" -f "${ERP_COMPOSE_FILE}" up -d backend frontend 2>&1 | tee -a "${LOG_FILE}"
    else
        # Green uses blue-green profile
        ${ERP_COMPOSE_CMD} --env-file "${ERP_ENV_FILE}" -f "${ERP_COMPOSE_FILE}" --profile blue-green up -d backend-green frontend-green 2>&1 | tee -a "${LOG_FILE}"
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
    
    # Test health endpoint (use wget which is in alpine)
    if ! docker exec "${backend_container}" wget -q --spider http://localhost:8000/health > /dev/null 2>&1; then
        error "Health check failed"
        return 1
    fi
    
    # Test readiness endpoint
    if ! docker exec "${backend_container}" wget -q --spider http://localhost:8000/ready > /dev/null 2>&1; then
        error "Readiness check failed"
        return 1
    fi
    
    # Test API root
    if ! docker exec "${backend_container}" wget -q --spider http://localhost:8000/ > /dev/null 2>&1; then
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
    local active_upstream_host="${NGINX_UPSTREAM_DIR_HOST}/upstream-active.conf"
    
    if [ ! -f "${new_upstream_host}" ]; then
        error "Upstream config not found: ${new_upstream_host}"
        return 1
    fi
    
    # Atomic switch - copy on host (not symlink in container since it's ro mount)
    if cp "${new_upstream_host}" "${active_upstream_host}" 2>&1 | tee -a "${LOG_FILE}"; then
        info "Upstream config updated on host"
    else
        error "Failed to update upstream config on host"
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
    
    # Store the OUTGOING version for rollback (the version we're leaving behind)
    if [ -f "${PREVIOUS_VERSION_FILE}" ]; then
        mv "${PREVIOUS_VERSION_FILE}" "${PREVIOUS_VERSION_FILE}.bak"
    fi
    echo "${VERSION}" > "${PREVIOUS_VERSION_FILE}"
    
    # Also store the image tag for true rollback
    local new_image="${DOCKER_USER:-powerrangeranikg}/erp-solution-backend:${VERSION}"
    echo "${new_image}" > "${PREVIOUS_IMAGE_FILE}"
}

stop_old_environment() {
    local color="$1"
    
    info "Stopping old ${color} environment"
    
    if [ "${color}" = "blue" ]; then
        # Blue is default - just stop services
        ${ERP_COMPOSE_CMD} --env-file "${ERP_ENV_FILE}" -f "${ERP_COMPOSE_FILE}" stop backend frontend 2>&1 | tee -a "${LOG_FILE}"
    else
        # Green uses blue-green profile
        ${ERP_COMPOSE_CMD} --env-file "${ERP_ENV_FILE}" -f "${ERP_COMPOSE_FILE}" --profile blue-green stop backend-green frontend-green 2>&1 | tee -a "${LOG_FILE}"
    fi
    
    success "Old ${color} environment stopped"
}

perform_rollback() {
    info "Performing rollback..."
    
    local current_color=$(get_active_color)
    local previous_color=$(get_inactive_color)
    local previous_version=""
    local previous_image=""
    
    if [ -f "${PREVIOUS_VERSION_FILE}" ]; then
        previous_version=$(cat "${PREVIOUS_VERSION_FILE}")
    else
        error "No previous version recorded for rollback"
        return 1
    fi
    
    if [ -f "${PREVIOUS_IMAGE_FILE}" ]; then
        previous_image=$(cat "${PREVIOUS_IMAGE_FILE}")
    else
        previous_image="${DOCKER_USER:-powerrangeranikg}/erp-solution-backend:${previous_version}"
    fi
    
    warn "Rolling back from ${current_color} to ${previous_color} (version: ${previous_version})"
    
    # Pull the previous image
    info "Pulling previous image: ${previous_image}"
    docker pull "${previous_image}" 2>&1 | tee -a "${LOG_FILE}"
    
    # Retag as current VERSION for the inactive color
    docker tag "${previous_image}" "${DOCKER_USER:-powerrangeranikg}/erp-solution-backend:${VERSION}" 2>&1 | tee -a "${LOG_FILE}"
    docker tag "${previous_image}" "${DOCKER_USER:-powerrangeranikg}/erp-solution-frontend:${VERSION}" 2>&1 | tee -a "${LOG_FILE}"
    
    # START the previous environment (it was stopped after the failed deploy)
    info "Starting previous environment: ${previous_color}"
    start_inactive_environment "${previous_color}"
    
    # Wait for it to be healthy
    if ! wait_for_health "${previous_color}"; then
        error "Previous environment failed health checks after rollback start"
        return 1
    fi
    
    # Run smoke tests on the rolled-back environment
    if ! run_smoke_tests "${previous_color}"; then
        error "Rollback environment failed smoke tests"
        return 1
    fi
    
    # Switch traffic back to the previous environment
    switch_traffic "${previous_color}" "$(get_active_color)"

    # Stop the failed environment (captured before the switch above, since
    # switch_traffic rewrites ACTIVE_COLOR_FILE)
    stop_old_environment "${current_color}"
    
    success "Rollback completed to ${previous_color} (version: ${previous_version})"
}

load_env() {
    if erp_detect_env_file; then
        info "Loading environment from ${ERP_ENV_FILE}"
        # Parsed rather than sourced: an env file is data, and a value holding
        # a space or a $ must not be able to run code as a side effect.
        erp_load_env "${ERP_ENV_FILE}"
        export ERP_ENV_FILE
    else
        error "No environment file found under ${ERP_DIR} (expected .env.production)."
        error "Create it with ./install.sh, or copy .env.production.template and fill it in."
        return 1
    fi
    # The env file's ENVIRONMENT/VERSION describe the application, not this
    # deploy. Restore the CLI arguments so validation and image selection see
    # what the operator asked for. CI depends on the second one when rolling
    # back to an older tag.
    ENVIRONMENT="${DEPLOY_TARGET_ENVIRONMENT}"
    VERSION="${DEPLOY_TARGET_VERSION}"
    export VERSION
}

main() {
    # Create log directory FIRST before any logging
    mkdir -p "$(dirname "${LOG_FILE}")"

    # Live values used throughout; load_env keeps these in sync with the CLI
    # arguments after it imports the env file.
    ENVIRONMENT="${DEPLOY_TARGET_ENVIRONMENT}"
    VERSION="${DEPLOY_TARGET_VERSION}"
    
    info "=========================================="
    info "ERP SOLUTION — Blue-Green Deployment"
    info "Environment: ${ENVIRONMENT}"
    info "Version: ${VERSION}"
    info "Rollback mode: ${ROLLBACK}"
    info "Log file: ${LOG_FILE}"
    info "=========================================="
    
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
            ${ERP_COMPOSE_CMD} --env-file "${ERP_ENV_FILE}" -f "${ERP_COMPOSE_FILE}" --profile blue-green stop backend-green frontend-green
        fi
        exit 1
    fi
    
    # Run smoke tests
    if ! run_smoke_tests "${inactive_color}"; then
        error "Smoke tests failed"
        if [ "${inactive_color}" = "green" ]; then
            ${ERP_COMPOSE_CMD} --env-file "${ERP_ENV_FILE}" -f "${ERP_COMPOSE_FILE}" --profile blue-green stop backend-green frontend-green
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