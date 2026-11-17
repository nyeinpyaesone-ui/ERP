#!/bin/bash
# ERP System Development Setup Script

set -e

echo "=== ERP System Development Setup ==="

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "Python version: $python_version"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Install pre-commit hooks
echo "Setting up pre-commit hooks..."
pre-commit install

# Copy environment file
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo ".env file created. Please update with your configuration."
fi

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p staticfiles logs

# Initialize database (if using Django)
echo "Setting up database..."
python src/manage.py migrate 2>/dev/null || echo "Django manage.py not found yet, skipping migrations."

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Update .env file with your configuration"
echo "3. Set up your PostgreSQL database"
echo "4. Run migrations: python src/manage.py migrate"
echo "5. Start development server: python src/manage.py runserver"
echo ""
