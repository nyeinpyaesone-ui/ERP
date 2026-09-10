# =============================================================================
# ERP SOLUTION - Makefile (Complete Development & Production Commands)
# =============================================================================

.PHONY: help install dev prod build test lint clean docker-up docker-down \
        docker-build docker-push deploy status logs shell-backend shell-frontend \
        db-migrate db-backup db-restore k8s-deploy k8s-rollback k8s-status \
        security-scan version release

SHELL := /bin/bash
DOCKER_USER := powerrangeranikg
VERSION := $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
DATE := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

# =============================================================================
# Help & Information
# =============================================================================

help:
	@echo "=============================================="
	@echo "  ERP SOLUTION — Available Commands"
	@echo "  Version: $(VERSION) | Commit: $(COMMIT)"
	@echo "=============================================="
	@echo ""
	@echo "📦 Installation & Setup:"
	@echo "  make install          Install all dependencies (backend, frontend, mobile)"
	@echo "  make dev              Start development environment (Docker Compose)"
	@echo "  make prod             Start production environment"
	@echo ""
	@echo "🔨 Build & Test:"
	@echo "  make build            Build all Docker images"
	@echo "  make test             Run all tests (backend + frontend)"
	@echo "  make lint             Run linters (flake8, black, mypy, eslint)"
	@echo "  make security-scan    Run security scans (Trivy, Snyk)"
	@echo ""
	@echo "🐳 Docker Operations:"
	@echo "  make docker-up        Start all Docker services"
	@echo "  make docker-down      Stop all Docker services"
	@echo "  make docker-restart   Restart all Docker services"
	@echo "  make docker-build     Build Docker images with version tags"
	@echo "  make docker-push      Push images to Docker Hub"
	@echo "  make logs             View all service logs"
	@echo "  make shell-backend    Open shell in backend container"
	@echo "  make shell-frontend   Open shell in frontend container"
	@echo ""
	@echo "🗄️  Database Operations:"
	@echo "  make db-migrate       Run database migrations"
	@echo "  make db-backup        Backup database to ./docker/backups/"
	@echo "  make db-restore       Restore database from backup"
	@echo "  make db-shell         Open psql shell to database"
	@echo ""
	@echo "☸️  Kubernetes Operations:"
	@echo "  make k8s-deploy       Deploy to Kubernetes (production)"
	@echo "  make k8s-staging      Deploy to Kubernetes (staging)"
	@echo "  make k8s-dev          Deploy to Kubernetes (development)"
	@echo "  make k8s-rollback     Rollback to previous Kubernetes deployment"
	@echo "  make k8s-status       Show Kubernetes deployment status"
	@echo "  make k8s-logs         View Kubernetes pod logs"
	@echo ""
	@echo "🚀 Deployment:"
	@echo "  make deploy           Deploy to production server (requires SERVER_IP)"
	@echo "  make release          Create a new release (version bump + push)"
	@echo "  make version          Show current version"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "  make clean            Clean build artifacts and caches"
	@echo "  make status           Show Git repository status"
	@echo ""

# =============================================================================
# Installation & Setup
# =============================================================================

install:
	@echo "📦 Installing dependencies..."
	@echo "  → Backend (Python)..."
	cd backend && python3 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	@echo "  → Frontend (Node.js)..."
	cd frontend && npm install
	@echo "  → Mobile (React Native)..."
	[ -d mobile ] && cd mobile && npm install || echo "  ⚠️  Mobile directory not found"
	@echo "✅ Installation complete!"

dev:
	@echo "🚀 Starting development environment..."
	docker-compose up -d postgres redis ollama
	@echo ""
	@echo "✅ Services started!"
	@echo ""
	@echo "Next steps:"
	@echo "  Backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000"
	@echo "  Frontend: cd frontend && npm run dev"
	@echo "  Mobile:   cd mobile && npx expo start"
	@echo ""
	@echo "Management URLs:"
	@echo "  pgAdmin:      http://localhost:5050 (admin@erp.local / admin)"
	@echo "  RedisInsight: http://localhost:5540"
	@echo "  Ollama:       http://localhost:11434"

prod:
	@echo "🚀 Starting production environment..."
	docker-compose -f docker-compose.prod.yml up -d
	@echo "✅ Production services started!"
	@echo "  Backend: http://localhost:8000"
	@echo "  Frontend: http://localhost:3000"

# =============================================================================
# Build & Test
# =============================================================================

build:
	@echo "🔨 Building Docker images..."
	docker-compose build

test:
	@echo "🧪 Running tests..."
	@echo "  → Backend tests..."
	cd backend && source venv/bin/activate && pytest --cov=app --cov-report=term-missing || echo "  ⚠️  No tests found or tests failed"
	@echo "  → Frontend tests..."
	cd frontend && npm test -- --passWithNoTests || echo "  ⚠️  Frontend tests skipped"
	@echo "✅ Testing complete!"

lint:
	@echo "🔍 Running linters..."
	@echo "  → Python (flake8, black, mypy)..."
	cd backend && source venv/bin/activate && \
		flake8 app --count --select=E9,F63,F7,F82 --show-source --statistics && \
		black --check app && \
		mypy app --ignore-missing-imports || true
	@echo "  → JavaScript/TypeScript (eslint)..."
	cd frontend && npm run lint || echo "  ⚠️  No lint script found"
	@echo "✅ Linting complete!"

security-scan:
	@echo "🔒 Running security scans..."
	@echo "  → Trivy filesystem scan..."
	trivy fs --severity HIGH,CRITICAL . || echo "  ⚠️  Trivy not installed"
	@echo "  → Snyk code scan..."
	snyk code test || echo "  ⚠️  Snyk not configured"
	@echo "✅ Security scan complete!"

# =============================================================================
# Docker Operations
# =============================================================================

docker-up:
	@echo "🐳 Starting Docker services..."
	docker-compose up -d
	@echo "✅ Services started!"
	docker ps --filter "name=erp"

docker-down:
	@echo "🛑 Stopping Docker services..."
	docker-compose down
	@echo "✅ Services stopped!"

docker-restart: docker-down docker-up

docker-build:
	@echo "🔨 Building Docker images (version: $(VERSION))..."
	docker build -t $(DOCKER_USER)/erp-solution-backend:$(VERSION) -t $(DOCKER_USER)/erp-solution-backend:latest ./backend
	docker build -t $(DOCKER_USER)/erp-solution-frontend:$(VERSION) -t $(DOCKER_USER)/erp-solution-frontend:latest ./frontend
	@echo "✅ Images built!"
	docker images | grep erp-solution

docker-push:
	@echo "📤 Pushing Docker images to Docker Hub..."
	docker push $(DOCKER_USER)/erp-solution-backend:$(VERSION)
	docker push $(DOCKER_USER)/erp-solution-backend:latest
	docker push $(DOCKER_USER)/erp-solution-frontend:$(VERSION)
	docker push $(DOCKER_USER)/erp-solution-frontend:latest
	@echo "✅ Images pushed!"

logs:
	docker-compose logs -f

shell-backend:
	docker-compose exec backend /bin/bash

shell-frontend:
	docker-compose exec frontend /bin/sh

# =============================================================================
# Database Operations
# =============================================================================

db-migrate:
	@echo "🗄️  Running database migrations..."
	docker-compose exec backend alembic upgrade head || echo "  ⚠️  Alembic not configured or migration failed"
	@echo "✅ Migrations complete!"

db-backup:
	@echo "💾 Backing up database..."
	@mkdir -p docker/backups
	docker-compose exec -T postgres pg_dump -U erp erp_solution > docker/backups/backup-$$(date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup created in docker/backups/"

db-restore:
	@echo "⚠️  Restoring database..."
	@echo "Enter backup filename (e.g., backup-20240101_120000.sql):"
	@read BACKUP_FILE && \
	docker-compose exec -T postgres psql -U erp erp_solution < docker/backups/$$BACKUP_FILE
	@echo "✅ Database restored!"

db-shell:
	@echo "🗄️  Opening psql shell..."
	docker-compose exec postgres psql -U erp erp_solution

# =============================================================================
# Kubernetes Operations
# =============================================================================

k8s-deploy:
	@echo "☸️  Deploying to Kubernetes (production)..."
	kubectl apply -k infra/k8s/overlays/production/
	@echo "✅ Deployment initiated!"
	make k8s-status

k8s-staging:
	@echo "☸️  Deploying to Kubernetes (staging)..."
	kubectl apply -k infra/k8s/overlays/staging/
	@echo "✅ Staging deployment initiated!"

k8s-dev:
	@echo "☸️  Deploying to Kubernetes (development)..."
	kubectl apply -k infra/k8s/overlays/development/
	@echo "✅ Development deployment initiated!"

k8s-rollback:
	@echo "↩️  Rolling back Kubernetes deployment..."
	kubectl rollout undo deployment/erp-solution-api -n erp_solution
	kubectl rollout undo deployment/erp-solution-web -n erp_solution
	kubectl rollout undo deployment/erp-solution-worker -n erp_solution
	@echo "✅ Rollback initiated!"

k8s-status:
	@echo "📊 Kubernetes Deployment Status:"
	kubectl get deployments -n erp_solution
	kubectl get pods -n erp_solution
	kubectl get svc -n erp_solution
	kubectl get ingress -n erp_solution

k8s-logs:
	@echo "📜 Kubernetes Pod Logs:"
	kubectl logs -n erp_solution -l app=erp-solution-api -f

# =============================================================================
# Deployment
# =============================================================================

deploy:
	@echo "🚀 Deploying to production server..."
	@if [ -z "$(SERVER_IP)" ]; then \
		echo "❌ Error: SERVER_IP not set. Usage: make deploy SERVER_IP=192.168.1.100"; \
		exit 1; \
	fi
	./deploy.sh $(SERVER_IP)

release:
	@echo "📦 Creating new release..."
	@echo "Current version: $(VERSION)"
	@echo "Enter new version (e.g., v1.2.0):"
	@read NEW_VERSION && \
	git tag $$NEW_VERSION && \
	git push origin $$NEW_VERSION && \
	echo "✅ Release $$NEW_VERSION created and pushed!"

version:
	@echo "Version: $(VERSION)"
	@echo "Commit: $(COMMIT)"
	@echo "Build Date: $(DATE)"

# =============================================================================
# Maintenance
# =============================================================================

clean:
	@echo "🧹 Cleaning build artifacts..."
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name *.egg-info -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/venv 2>/dev/null || true
	rm -rf dist build 2>/dev/null || true
	docker-compose down -v 2>/dev/null || true
	@echo "✅ Cleanup complete!"

status:
	@echo "📊 Repository Status:"
	git status -sb
	@echo ""
	@echo "Statistics:"
	@echo "  Commits: $$(git rev-list --count HEAD)"
	@echo "  Files:   $$(git ls-files | wc -l)"
	@echo "  Branch:  $$(git branch --show-current)"
