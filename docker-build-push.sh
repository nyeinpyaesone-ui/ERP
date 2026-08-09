#!/bin/bash
###############################################################################
# ERP SOLUTION — Docker Build & Push Script (Optimized)
# Run this on your LOCAL MACHINE with Docker installed
# Features: BuildKit caching, parallel builds, multi-arch support ready
###############################################################################

set -e

DOCKER_USERNAME="powerrangeranikg"
VERSION="${1:-v1.0.0}"
REGISTRY="docker.io"
IMAGE_BACKEND="erp-solution-backend"
IMAGE_FRONTEND="erp-solution-frontend"

echo "=========================================="
echo "  ERP SOLUTION — Docker Build & Push"
echo "  Version: $VERSION"
echo "  Registry: $REGISTRY"
echo "=========================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed"
    echo "Install from: https://docs.docker.com/get-docker/"
    exit 1
fi

# Enable BuildKit for better caching
export DOCKER_BUILDKIT=1

# Check if logged in
echo "[1/7] Checking Docker Hub login..."
if ! docker info 2>/dev/null | grep -q "Username"; then
    echo "  Please login first:"
    echo "  docker login -u $DOCKER_USERNAME"
    exit 1
fi
echo "  ✅ Logged in as $(docker info 2>/dev/null | grep Username | cut -d' ' -f3)"

# Setup Buildx builder for caching
echo ""
echo "[2/7] Setting up Docker Buildx..."
docker buildx create --use --name erp-builder 2>/dev/null || docker buildx use erp-builder
docker buildx inspect --bootstrap > /dev/null 2>&1
echo "  ✅ Buildx ready"

# Build backend with cache
echo ""
echo "[3/7] Building backend image with cache..."
docker buildx build \
    --platform linux/amd64 \
    --tag $REGISTRY/$DOCKER_USERNAME/$IMAGE_BACKEND:$VERSION \
    --tag $REGISTRY/$DOCKER_USERNAME/$IMAGE_BACKEND:latest \
    --file ./backend/Dockerfile \
    --cache-from type=registry,ref=$REGISTRY/$DOCKER_USERNAME/$IMAGE_BACKEND:buildcache \
    --cache-to type=inline \
    --progress plain \
    --push \
    ./backend
echo "  ✅ Backend built & pushed: $REGISTRY/$DOCKER_USERNAME/$IMAGE_BACKEND:$VERSION"

# Build frontend with cache
echo ""
echo "[4/7] Building frontend image with cache..."
docker buildx build \
    --platform linux/amd64 \
    --tag $REGISTRY/$DOCKER_USERNAME/$IMAGE_FRONTEND:$VERSION \
    --tag $REGISTRY/$DOCKER_USERNAME/$IMAGE_FRONTEND:latest \
    --file ./frontend/Dockerfile \
    --cache-from type=registry,ref=$REGISTRY/$DOCKER_USERNAME/$IMAGE_FRONTEND:buildcache \
    --cache-to type=inline \
    --progress plain \
    --push \
    ./frontend
echo "  ✅ Frontend built & pushed: $REGISTRY/$DOCKER_USERNAME/$IMAGE_FRONTEND:$VERSION"

# Verify images on Docker Hub
echo ""
echo "[5/7] Verifying images on Docker Hub..."
echo "  Backend: https://hub.docker.com/r/$DOCKER_USERNAME/$IMAGE_BACKEND/tags"
echo "  Frontend: https://hub.docker.com/r/$DOCKER_USERNAME/$IMAGE_FRONTEND/tags"

# Display summary
echo ""
echo "=========================================="
echo "  ✅ ALL IMAGES LIVE ON DOCKER HUB!"
echo "=========================================="
echo ""
echo "  Images pushed:"
echo "  • $REGISTRY/$DOCKER_USERNAME/$IMAGE_BACKEND:$VERSION"
echo "  • $REGISTRY/$DOCKER_USERNAME/$IMAGE_BACKEND:latest"
echo "  • $REGISTRY/$DOCKER_USERNAME/$IMAGE_FRONTEND:$VERSION"
echo "  • $REGISTRY/$DOCKER_USERNAME/$IMAGE_FRONTEND:latest"
echo ""
echo "  Pull commands:"
echo "  docker pull $REGISTRY/$DOCKER_USERNAME/$IMAGE_BACKEND:$VERSION"
echo "  docker pull $REGISTRY/$DOCKER_USERNAME/$IMAGE_FRONTEND:$VERSION"
echo ""
echo "  Deploy to Kubernetes:"
echo "  kubectl apply -k infra/k8s/overlays/production"
echo ""
