.PHONY: help install dev build test clean docker-up docker-down push

help:
	@echo "ERP SOLUTION — Available Commands"
	@echo ""
	@echo "  make install      Install all dependencies"
	@echo "  make dev          Start development environment"
	@echo "  make build        Build production images"
	@echo "  make test         Run all tests"
	@echo "  make clean        Clean build artifacts"
	@echo "  make docker-up    Start Docker services"
	@echo "  make docker-down  Stop Docker services"
	@echo "  make push         Push to GitHub"
	@echo "  make status       Show repository status"

install:
	cd backend && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
	cd backend/frontend-react && npm install
	cd mobile && npm install

dev:
	docker-compose up -d postgres redis
	@echo "Start backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
	@echo "Start frontend: cd backend/frontend-react && npm run dev"
	@echo "Start mobile:   cd mobile && npx expo start"

test:
	cd backend && ./venv/bin/python -m pytest
	cd backend/frontend-react && npm test

clean:
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

push:
	git add -A
	git commit -m "update: $(shell date '+%Y-%m-%d %H:%M')" || true
	git push origin main

status:
	git status -sb
	@echo "Commits: $$(git rev-list --count HEAD)"
	@echo "Files:   $$(git ls-files | wc -l)"
