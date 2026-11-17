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

The exact names are consumed by .github/workflows/ci.yml. Configure repository-level
Actions secrets with scripts/configure-github-actions.sh:

| Secret | Scope |
|---|---|
| DOCKER_PAT_BACKEND / DOCKER_PAT_FRONTEND | Separate image-scoped Docker Hub push tokens |
| STAGING_SSH_PRIVATE_KEY / PRODUCTION_SSH_PRIVATE_KEY | Separate, dedicated, unencrypted deploy keys |
| STAGING_KNOWN_HOSTS / PRODUCTION_KNOWN_HOSTS | Out-of-band verified pinned host keys |
| STAGING_HOST / STAGING_USER | Staging host and non-root deploy account |
| PRODUCTION_HOST / PRODUCTION_USER | Production host and non-root deploy account |

### Required Variables (GitHub)

| Variable | Purpose |
|---|---|
| DOCKER_USER | Docker Hub namespace |
| STAGING_DOMAIN | Staging deployment URL hostname |
| PRODUCTION_DOMAIN | Production deployment URL hostname |

Database, Redis, JWT and integration credentials are runtime host configuration,
not GitHub Actions secrets. Keep independent .env.staging and .env.production
files on their respective hosts, mode 0600.

DOCKER_USER is mandatory. Compose and deployment scripts do not silently fall
back to a personal Docker Hub namespace.

## Initial Server Setup

Provision staging and production on **separate hosts**. The current Compose
stack uses fixed container names and must not share one host between these
environments.

### Production host

```bash
git clone git@github.com:nyeinpyaesone-ui/ERP.git /opt/erp-solution
cd /opt/erp-solution
sudo ./install.sh erp.example.com ops@example.com
```

The installer generates unique DB, Redis and application secrets, prompts for
the Docker Hub namespace, and writes /opt/erp-solution/.env.production with
mode 0600. Use the real production domain and contact email. Configure a
read-only Docker Hub credential on the host using its credential helper.

### Staging host

```bash
git clone git@github.com:nyeinpyaesone-ui/ERP.git /opt/erp-solution
cd /opt/erp-solution
install -m 0600 .env.staging.template /opt/erp-solution/.env.staging
```

Replace every CHANGE_ME value with unique staging-only values, set the real
staging CORS origin and the configured Docker Hub namespace, then confirm
permissions remain 0600. Configure a separate read-only Docker Hub credential.
Never copy production secrets into staging.

The GitHub Actions bootstrapper configures repository variables/secrets and
Environment ref policies; it does not create host files or deploy. See
docs/GITHUB_SECRETS.md before the first deployment.

## Deployment Commands

### Using Make

`make` only covers local development (see `make help`): `install`, `dev`,
`build`, `test`, `lint`, `clean`, `docker-up`, `docker-down`, `push`, `status`.
There is no `deploy-*`, `rollback` or `logs-*` target — deployment runs from
`scripts/`, which you invoke directly.

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

# Manual SSL renewal (setup-ssl.sh writes this onto the server; there is no
# copy of it in the repo)
/opt/erp-solution/scripts/renew-ssl.sh
```

### Using GitHub Actions

The CI workflow builds and tests on pushes; pushes do not deploy automatically.
Staging requires a manual CI dispatch on main with deploy_staging=true.
Production requires a manual CI dispatch on a v* tag with
deploy_production=true. The Release workflow publishes a GitHub Release after
the tag's CI run succeeds and both immutable Docker images are verified.

Run bash scripts/configure-github-actions.sh to provision repository
variables/secrets and GitHub Environment ref policies. Actual host runtime env
files and read-only Docker Hub pull credentials are configured separately.

## Blue-Green Deployment Details

### How It Works

1. **Two Colors per Host**: Blue (active) and Green (inactive); staging and production are separate hosts
2. **Shared Database**: Both environments use the same PostgreSQL/Redis
3. **Traffic Switch**: Nginx upstream file is updated in place, validated, and reloaded; the previous file is retained for rollback
4. **Health Verification**: Comprehensive checks before switch
5. **Rollback**: Restore the exact previous Nginx upstream file if validation or post-switch checks fail

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
5. Update and validate the Nginx upstream file, then reload Nginx
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
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Create new migration
docker compose -f docker-compose.prod.yml exec backend alembic revision --autogenerate -m "description"

# Check migration status
docker compose -f docker-compose.prod.yml exec backend alembic current
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
docker compose -f docker-compose.prod.yml logs -f --tail=100

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend --tail=100

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
docker compose -f docker-compose.prod.yml exec -T postgres psql -U erp erp_solution < backup.sql

# Restore environment
cp backup/backend.env /opt/erp-solution/.env.production
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Backend unhealthy | Check logs: `docker logs erp-blue-backend` |
| Nginx 502 Bad Gateway | Verify backend container is running and healthy |
| SSL certificate expired | Run `/opt/erp-solution/scripts/renew-ssl.sh` on the server |
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
- [ ] Separate non-root SSH deploy users and distinct keys for staging/production
- [ ] Pinned known_hosts verified out-of-band
- [ ] GitHub Environments restricted to main and v* refs
- [ ] Production required reviewer configured when independent approval is required
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