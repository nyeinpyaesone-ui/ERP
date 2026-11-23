# Environment Setup Guide

## 1. Prerequisites
- Python 3.9+
- PostgreSQL 14+
- Redis 6+
- Node.js 18+ (for frontend assets)
- Docker & Docker Compose (optional)

## 2. Local Development Setup

### Step 1: Clone Repository
```bash
git clone <repository-url>
cd erp-system
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Environment Variables
```bash
cp .env.example .env
# Edit .env with your local settings
```

### Step 5: Database Setup
```bash
# Create database
createdb erp_dev

# Run migrations
python src/manage.py migrate

# Create superuser
python src/manage.py createsuperuser
```

### Step 6: Start Development Server
```bash
python src/manage.py runserver
```

## 3. Docker Setup (Alternative)

### Start All Services
```bash
docker-compose up -d
```

### Run Migrations
```bash
docker-compose exec web python src/manage.py migrate
```

### Create Superuser
```bash
docker-compose exec web python src/manage.py createsuperuser
```

## 4. Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| DEBUG | Debug mode | True |
| SECRET_KEY | Django secret key | (required) |
| DATABASE_URL | PostgreSQL connection | postgresql://localhost/erp_dev |
| REDIS_URL | Redis connection | redis://localhost:6379/0 |
| ALLOWED_HOSTS | Allowed domains | localhost,127.0.0.1 |

## 5. Verification
```bash
# Run tests
pytest

# Check code quality
flake8 src/
black --check src/

# Access application
open http://localhost:8000
```

## 6. Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
pg_isready

# Restart PostgreSQL (Mac)
brew services restart postgresql
```

### Migration Issues
```bash
# Reset migrations (dev only)
python src/manage.py migrate --run-syncdb
```
