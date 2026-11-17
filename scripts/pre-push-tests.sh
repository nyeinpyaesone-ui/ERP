#!/bin/bash
# Pre-push test script
# Run this before pushing to catch issues early

set -e

echo "=========================================="
echo "Running Pre-Push Checks"
echo "=========================================="

echo ""
echo "[1/5] Running tests..."
pytest --cov=src --cov-fail-under=80 -q

echo ""
echo "[2/5] Checking code formatting (Black)..."
black --check src/

echo ""
echo "[3/5] Checking import order (isort)..."
isort --check-only src/

echo ""
echo "[4/5] Running linter (Flake8)..."
flake8 src/

echo ""
echo "[5/5] Running security scan (Bandit)..."
bandit -r src/ -q

echo ""
echo "=========================================="
echo "✅ All checks passed!"
echo "=========================================="
