#!/bin/bash
###############################################################################
# ERP SOLUTION — CI/CD Test Script
# Usage: ./scripts/test-cicd.sh
###############################################################################

set -e

C='[0;36m'; G='[0;32m'; Y='[1;33m'; R='[0;31m'; NC='[0m'

info()  { echo -e "${C}[INFO]${NC} $1"; }
ok()    { echo -e "${G}[PASS]${NC} $1"; }
warn()  { echo -e "${Y}[WARN]${NC} $1"; }
err()   { echo -e "${R}[FAIL]${NC} $1"; }

echo "=========================================="
echo "  ERP SOLUTION — CI/CD Pipeline Test"
echo "=========================================="
echo ""

# Test 1: Git repository
info "[1/8] Testing Git repository..."
if [ -d ".git" ]; then
    ok "Git repository exists"
else
    err "Git repository not found"
    exit 1
fi

# Test 2: GitHub remote
info "[2/8] Testing GitHub remote..."
if git remote get-url origin &>/dev/null; then
    remote=$(git remote get-url origin)
    ok "Remote configured: $remote"
else
    err "GitHub remote not configured"
    exit 1
fi

# Test 3: GitHub Actions workflows
info "[3/8] Testing GitHub Actions workflows..."
if [ -f ".github/workflows/ci.yml" ]; then
    ok "CI workflow exists"
else
    err "CI workflow missing"
fi

if [ -f ".github/workflows/release.yml" ]; then
    ok "Release workflow exists"
else
    err "Release workflow missing"
fi

# Test 4: Docker files
info "[4/8] Testing Docker configuration..."
if [ -f "docker-compose.yml" ]; then
    ok "docker-compose.yml exists"
else
    err "docker-compose.yml missing"
fi

if [ -f "backend/Dockerfile" ] || [ -f "backend/docker/Dockerfile" ]; then
    ok "Backend Dockerfile exists"
else
    warn "Backend Dockerfile not found (may be in subdir)"
fi

if [ -f "frontend/Dockerfile" ] || [ -f "frontend/docker/Dockerfile" ]; then
    ok "Frontend Dockerfile exists"
else
    warn "Frontend Dockerfile not found (may be in subdir)"
fi

# Test 5: Docker build test
info "[5/8] Testing Docker build..."
if command -v docker &>/dev/null; then
    ok "Docker installed"

    # Try building backend
    if [ -f "backend/Dockerfile" ]; then
        info "Building backend image..."
        if docker build -t erp-solution-backend:test ./backend &>/dev/null; then
            ok "Backend image builds successfully"
        else
            warn "Backend build failed (may need dependencies)"
        fi
    fi

    # Try building frontend
    if [ -f "frontend/Dockerfile" ]; then
        info "Building frontend image..."
        if docker build -t erp-solution-frontend:test ./frontend &>/dev/null; then
            ok "Frontend image builds successfully"
        else
            warn "Frontend build failed (may need dependencies)"
        fi
    fi
else
    warn "Docker not installed"
fi

# Test 6: GitHub secrets check
info "[6/8] Checking GitHub secrets..."
# Note: Can't actually check secrets from local, but we can verify the workflow expects them
if grep -q "secrets.DOCKER_USERNAME" .github/workflows/release.yml 2>/dev/null; then
    ok "Workflow expects DOCKER_USERNAME secret"
else
    warn "Workflow may not use DOCKER_USERNAME"
fi

if grep -q "secrets.DOCKER_PASSWORD" .github/workflows/release.yml 2>/dev/null; then
    ok "Workflow expects DOCKER_PASSWORD secret"
else
    warn "Workflow may not use DOCKER_PASSWORD"
fi

# Test 7: Tag creation test
info "[7/8] Testing tag creation..."
if git tag -l | grep -q "v1.0.0"; then
    ok "v1.0.0 tag exists"
else
    warn "v1.0.0 tag not found"
fi

if git tag -l | grep -q "v1.1.0-dev"; then
    ok "v1.1.0-dev tag exists"
else
    warn "v1.1.0-dev tag not found"
fi

# Test 8: Push simulation
info "[8/8] Simulating release push..."
echo ""
echo "To test the full CI/CD pipeline, run:"
echo "  git tag v1.1.0"
echo "  git push origin v1.1.0"
echo ""
echo "Then check: https://github.com/nyeinpyaesone-ui/ERP/actions"
echo ""

# Summary
echo "=========================================="
echo "  CI/CD Test Summary"
echo "=========================================="
echo ""
echo "Manual test steps:"
echo "  1. Add DOCKER_USERNAME and DOCKER_PASSWORD to GitHub Secrets"
echo "  2. Create repositories on Docker Hub:"
echo "     - powerrangeranikg/erp-solution-backend"
echo "     - powerrangeranikg/erp-solution-frontend"
echo "  3. Push tag: git tag v1.1.0 && git push origin v1.1.0"
echo "  4. Watch pipeline at: https://github.com/nyeinpyaesone-ui/ERP/actions"
echo ""
echo "Expected results:"
echo "  ✅ CI workflow runs tests"
echo "  ✅ Release workflow builds and pushes Docker images"
echo "  ✅ Images appear on Docker Hub"
echo ""
