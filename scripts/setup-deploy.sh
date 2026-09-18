#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Deployment Setup Script
# Creates necessary directory structure for blue-green deployment
###############################################################################

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ERP_DIR="/opt/erp-solution"

info() { echo -e "\033[0;34m[INFO]\033[0m $*"; }
success() { echo -e "\033[0;32m[SUCCESS]\033[0m $*"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
error() { echo -e "\033[0;31m[ERROR]\033[0m $*"; }

main() {
    info "Setting up ERP Solution deployment structure..."
    
    # Create /opt/erp-solution directories
    sudo mkdir -p "${ERP_DIR}/logs"
    sudo mkdir -p "${ERP_DIR}/ssl"
    sudo mkdir -p "${ERP_DIR}/backups"
    
    # Set permissions
    sudo chown -R $USER:$USER "${ERP_DIR}"
    
    # Copy nginx upstream configs to host nginx directory (if using host nginx)
    # For container nginx, they're mounted from ./nginx/
    info "Nginx upstream configs are in ${PROJECT_ROOT}/nginx/"
    ls -la "${PROJECT_ROOT}/nginx/upstream-*.conf"
    
    # Create initial active color file if not exists
    if [ ! -f "${ERP_DIR}/.active_color" ]; then
        echo "blue" > "${ERP_DIR}/.active_color"
        info "Created initial active color: blue"
    fi
    
    # Create docker networks if they don't exist
    if ! docker network ls | grep -q "erp-network"; then
        docker network create erp-network
        info "Created docker network: erp-network"
    fi
    
    # Copy SSL certificates (if available)
    if [ -f "${PROJECT_ROOT}/ssl/cert.pem" ] && [ -f "${PROJECT_ROOT}/ssl/key.pem" ]; then
        cp "${PROJECT_ROOT}/ssl/cert.pem" "${ERP_DIR}/ssl/"
        cp "${PROJECT_ROOT}/ssl/key.pem" "${ERP_DIR}/ssl/"
        info "SSL certificates copied to ${ERP_DIR}/ssl/"
    else
        warn "SSL certificates not found in ${PROJECT_ROOT}/ssl/"
        warn "You'll need to add them before enabling HTTPS"
    fi
    
    success "Deployment structure setup complete!"
    info ""
    info "Next steps:"
    info "1. Add SSL certificates to ${ERP_DIR}/ssl/ (cert.pem and key.pem)"
    info "2. Configure your domain DNS to point to this server"
    info "3. Run deployment: ./scripts/deploy-blue-green.sh production v1.0.0"
    info "4. For rollback: ./scripts/deploy-blue-green.sh production v1.0.0 --rollback"
}

main "$@"