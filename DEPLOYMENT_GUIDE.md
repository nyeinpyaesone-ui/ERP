# ERP SOLUTION — Deployment Guide

This document covers the complete deployment process for the ERP SOLUTION application using the blue-green deployment strategy.

## Overview

The deployment system uses:
- **Blue-Green Deployment**: Zero-downtime deployments with instant rollback capability
- **Docker Compose**: Container orchestration for production
- **Nginx**: Reverse proxy with SSL termination
- **Let's Encrypt**: Automated SSL certificate management
- **GitHub Actions**: CI/CD pipeline with automated testing and deployment

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Nginx (SSL)                             │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │  api.domain.com │  │ app.domain.com  │                   │
│  └────────┬────────┘  └────────┬────────┘                   │
└───────────┼────────────────────┼────────────────────────────┘
            │                    │
            ▼                    ▼
    ┌───────────────┐    ┌───────────────┐
    │   Backend     │    │   Frontend    │
    │  (Blue/Green) │    │  (Blue/Green) │
    └───────┬───────┘    └───────┬───────┘
            │                    │
            └────────┬───────────┘
                     ▼
    ┌────────────────────────────────┐
    │     Shared Services            │
    │  PostgreSQL  │  Redis  │Ollama │
    └────────────────────────────────┘
```

## Prerequisites

### Server Requirements
- **OS**: Ubuntu 22.04+ / Debian 12+ (systemd)
- **Docker**: 24.0+ with Docker Compose plugin
- **Memory**: Minimum 4GB RAM (8GB recommended)
- **Disk**: Minimum 50GB free space
- **Ports**: 80, 443, 22 (SSH) open

### Required Secrets (GitHub)
Configure these in GitHub repository settings → Secrets and variables → Actions:

| Secret | Description |
|--------|-------------|
| `DOCKER_PAT_BACKEND` | Docker Hub PAT for backend images |
| `DOCKER_PAT_FRONTEND` | Docker Hub PAT for frontend images |
| `DB_PASSWORD` | PostgreSQL password |
| `REDIS_PASSWORD` | Redis password |
| `SECRET_KEY` | JWT secret (32+ chars) |
| `CORS_ORIGINS_PROD` | Production CORS origins |
| `CORS_ORIGINS_STAGING` | Staging CORS origins |
| `API_URL_PROD` | Production API URL |
| `API_URL_STAGING` | Staging API URL |
| `WS_URL_PROD` | Production WebSocket URL |
| `WS_URL_STAGING` | Staging WebSocket URL |
| `SSH_PRIVATE_KEY_PROD` | SSH private key for production |
| `SSH_PRIVATE_KEY_STAGING` | SSH private key for staging |
| `SSH_HOST_PROD` | Production server hostname/IP |
| `SSH_HOST_STAGING` | Staging server hostname/IP |
| `SSH_USER_PROD` | Production SSH user |
| `SSH_USER_STAGING` | Staging SSH user |

### Required Variables (GitHub)
Configure these in GitHub repository settings → Variables:

| Variable | Description |
|----------|-------------|
| `DOCKER_USER` | Docker Hub username |
| `STAGING_DOMAIN` | Staging domain (e.g., staging.yourdomain.com) |
| `PRODUCTION_DOMAIN` | Production domain (e.g., api.yourdomain.com) |

## Initial Server Setup

Run once on new servers:

```bash
# 1. Clone repository
git clone https://github.com/yourorg/erp-solution.git /opt/erp-solution
cd /opt/erp-solution

# 2. Create environment file
cp .env.example .env.production
# Edit .env.production with all required values

# 3. Create SSL directory
mkdir -p /opt/erp-solution/ssl /opt/erp-solution/logs/nginx /opt/erp-solution/backups

# 4. Run initial SSL setup (first time only)
./scripts/setup-ssl.sh api.yourdomain.com admin@yourdomain.com

# 5. Start production stack
docker-compose -f docker-compose.prod.yml up -d

# 6. Verify deployment
curl https://api.yourdomain.com/health
curl https://api.yourdomain.com/ready
```

## Deployment Commands

### Using Make (Recommended)

```bash
# Deploy to staging (auto on push to main)
make deploy-staging

# Deploy specific version to production
make deploy-production VERSION=v1.2.3

# Deploy latest to production
make deploy-production

# Rollback production
make rollback

# Rollback to specific version
make rollback VERSION=v1.2.2

# View logs
make logs
make logs-backend
make logs-frontend
```

### Using Scripts Directly

```bash
# Blue-green deployment
./scripts/deploy-blue-green.sh production v1.2.3

# Rollback
./scripts/rollback.sh production

# Rollback to specific version
./scripts/rollback.sh production v1.2.2

# SSL setup
./scripts/setup-ssl.sh api.yourdomain.com admin@yourdomain.com

# Manual SSL renewal
./scripts/renew-ssl.sh
```

### Using GitHub Actions

1. **Automatic Staging**: Push to `main` branch → auto-deploys to staging
2. **Production Release**: Create git tag `v1.2.3` → triggers production deploy
3. **Manual Deploy**: Actions → Deploy workflow → Run workflow
4. **Rollback**: Actions → Deploy workflow → Run with `rollback: true`

## Blue-Green Deployment Details

### How It Works

1. **Two Environments**: Blue (active) and Green (staging)
2. **Shared Database**: Both environments use the same PostgreSQL/Redis
3. **Traffic Switch**: Nginx upstream symlink swap (< 1 second)
4. **Health Verification**: Comprehensive checks before switch
5. **Instant Rollback**: Swap symlink back if issues detected

### Container Naming

| Environment | Backend Container | Frontend Container |
|-------------|-------------------|---------------------|
| Blue (active) | `erp-blue-backend` | `erp-blue-frontend` |
| Green (staging) | `erp-green-backend` | `erp-green-frontend` |

### Deployment Flow

```
1. Pull new images for inactive color
        │
        ▼
2. Start inactive environment containers
        │
        ▼
3. Wait for health checks (up to 5 minutes)
        │
        ▼
4. Run smoke tests (health, ready, API root)
        │
        ▼
5. Switch Nginx upstream (atomic symlink)
        │
        ▼
6. Verify post-switch with external checks
        │
        ▼
7. Stop old environment containers
        │
        ▼
8. Send notifications
```

### Rollback Flow

```
1. Identify previous version from .previous_version
        │
        ▼
2. Start previous environment if not running
        │
        ▼
3. Verify health and run smoke tests
        │
        ▼
4. Switch Nginx upstream back
        │
        ▼
5. Stop failed environment
        │
        ▼
6. Send rollback notification
```

## SSL Certificate Management

### Automatic Setup (First Time)

```bash
./scripts/setup-ssl.sh api.yourdomain.com admin@yourdomain.com
```

This will:
1. Generate nginx configuration for the domain
2. Obtain Let's Encrypt certificate
3. Set up automatic daily renewal (cron at 3 AM)
4. Configure nginx to use the certificate
5. Reload nginx

### Manual Renewal

```bash
# Trigger manual renewal check
/opt/erp-solution/scripts/renew-ssl.sh

# Check renewal logs
cat /opt/erp-solution/logs/ssl-renewal-$(date +%Y%m%d).log
```

### Staging Environment (Using --staging)

```bash
# For testing SSL setup without rate limits
./scripts/setup-ssl.sh staging.yourdomain.com admin@yourdomain.com --staging
```

## Database Migrations

Migrations run automatically on container startup via `entrypoint.sh`:

```bash
# Manual migration (if needed)
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Create new migration
docker-compose -f docker-compose.prod.yml exec backend alembic revision --autogenerate -m "description"

# Check migration status
docker-compose -f docker-compose.prod.yml exec backend alembic current
```

## Monitoring & Health Checks

### Health Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `/health` | Liveness | `{"status": "healthy"}` |
| `/ready` | Readiness | `{"status": "ready", "checks": {...}}` |

### Docker Health Checks

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/ready"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Viewing Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f --tail=100

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend --tail=100

# Nginx access logs
docker exec erp-nginx tail -f /var/log/nginx/access.log

# Deployment logs
cat /opt/erp-solution/logs/deploy-*.log
```

## Backup & Recovery

### Automated Backup

```bash
# Run backup
./scripts/backup.sh

# Backup to specific directory
./scripts/backup.sh /mnt/backups
```

Backup includes:
- Source code (excluding .git, node_modules, venv)
- PostgreSQL database dump
- Environment files
- Manifest with version info

### Recovery

```bash
# Restore database
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U erp erp_solution < backup.sql

# Restore environment
cp backup/backend.env /opt/erp-solution/.env.production
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Backend unhealthy | Check logs: `docker logs erp-blue-backend` |
| Nginx 502 Bad Gateway | Verify backend container is running and healthy |
| SSL certificate expired | Run `./scripts/renew-ssl.sh` |
| Database connection failed | Verify PostgreSQL is running and credentials correct |
| Deployment stuck | Check deployment logs in `/opt/erp-solution/logs/` |

### Debug Commands

```bash
# Check container status
docker ps -a --filter name=erp-

# Inspect container health
docker inspect erp-blue-backend --format='{{.State.Health.Status}}'

# Test backend directly
docker exec erp-blue-backend curl http://localhost:8000/ready

# Test nginx config
docker exec erp-nginx nginx -t

# Check active upstream
cat /opt/erp-solution/.active_color

# View nginx upstream config
docker exec erp-nginx cat /etc/nginx/conf.d/upstream-active.conf
```

### Rollback Not Working

```bash
# Manual rollback steps
# 1. Check previous version
cat /opt/erp-solution/.previous_version

# 2. Check active color
cat /opt/erp-solution/.active_color

# 3. Manually switch upstream
docker exec erp-nginx ln -sf /etc/nginx/conf.d/upstream-blue.conf /etc/nginx/conf.d/upstream-active.conf
docker exec erp-nginx nginx -s reload

# 4. Update active color
echo "blue" > /opt/erp-solution/.active_color
```

## Security Checklist

- [ ] All secrets stored in GitHub Secrets (not in repo)
- [ ] `.env.production` not committed to git
- [ ] SSL certificates valid and auto-renewing
- [ ] Database passwords strong and unique
- [ ] Redis password set
- [ ] JWT secret 32+ characters
- [ ] CORS origins restricted to known domains
- [ ] SSH keys for deployment are dedicated (not personal)
- [ ] GitHub Environments configured for production approval
- [ ] Dependabot alerts enabled and monitored

## Performance Tuning

### Backend
- Increase `pool_size` in `database.py` for high concurrency
- Enable Redis caching for frequent queries
- Configure `uvicorn` workers: `--workers 4`

### Nginx
- Adjust `worker_connections` based on CPU cores
- Enable `gzip` for API responses
- Configure proxy buffering for large responses

### Database
- Run `ANALYZE` after large data imports
- Configure `shared_buffers` = 25% RAM
- Enable `pg_stat_statements` for query analysis

## Support

For deployment issues:
1. Check deployment logs: `/opt/erp-solution/logs/deploy-*.log`
2. Review GitHub Actions workflow run
3. Check container health and logs
4. Verify environment variables in `.env.production`
5. Contact DevOps team with deployment ID and error details