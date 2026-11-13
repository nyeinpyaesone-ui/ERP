# Production Deployment Guide

## Architecture Overview

```
┌─────────────────────────────────────────┐
│              Load Balancer              │
│         (NGINX / AWS ALB / Cloudflare)   │
└─────────────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───┴───┐   ┌──────┴──────┐  ┌───┴───┐
│ Web   │   │  API        │  │ Web   │
│ (CDN) │   │  (FastAPI)  │  │ (CDN) │
└───┬───┘   └──────┬──────┘  └───┬───┘
    │              │              │
    └──────────────┼──────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───┴───┐   ┌──────┴──────┐  ┌───┴───┐
│Postgre│   │   Redis     │  │Ollama │
│SQL 15 │   │   Cache     │  │ AI    │
└───────┘   └─────────────┘  └───────┘
```

## Deployment Options

### Option 1: Docker Compose (Single Server)

```bash
# 1. Clone repository
git clone https://github.com/nyeinpyaesone-ui/ERP.git
cd ERP

# 2. Prepare the protected install directory and generate a production env file
install -d -m 0750 /opt/erp-solution
bash scripts/configure-environment.sh \
  --environment production \
  --domain <production-domain> \
  --docker-user <docker-hub-namespace> \
  --version <published-v-tag> \
  --dir /opt/erp-solution
# The generated .env.production is mode 0600 and contains unique random secrets.

# 3. Configure read-only Docker Hub access on this host.
# First install/configure a native Docker credential helper.
bash scripts/configure-host-registry.sh \
  --docker-user <docker-hub-namespace> \
  --image-tag <published-v-tag>

# 4. Start production stack
docker compose --env-file /opt/erp-solution/.env.production -f /opt/erp-solution/docker-compose.prod.yml up -d

# 5. Run migrations
docker compose --env-file /opt/erp-solution/.env.production -f /opt/erp-solution/docker-compose.prod.yml exec backend alembic upgrade head

# 6. Verify (nginx is the only published port in the prod stack)
curl http://localhost/api/v1/health
```

### Environment isolation

The active blue-green Compose stack uses fixed container names. Staging and
production must therefore be deployed to **separate Docker hosts**. Generate
`.env.staging` on the staging host and `.env.production` on the production
host with `scripts/configure-environment.sh`; do not copy one file between
hosts. The application setting is `ENVIRONMENT=prod` in both files because
the backend accepts only `dev|test|prod`. The deploy target controls which
environment-specific file is selected.

Do not commit real env files. They contain independent PostgreSQL, Redis, and
application secrets and must remain mode `0600`.

### Option 2: Kubernetes manifests (separate, not CI-integrated)

The manifests under `infra/k8s/` are a separate deployment scaffold. They are
**not** the deployment target of the current CI workflow: CI publishes
Docker Hub Compose images, while the Kubernetes manifests reference different
GHCR images. The manifests also have outstanding runtime issues documented in
`infra/k8s/README-Kubernetes.md`.

Do not apply these manifests to production until the GHCR image pipeline,
container runtime contract, Redis authentication, backup tooling, storage,
Ingress, and cluster prerequisites have been implemented and validated.

Read-only validation:

```bash
kubectl config current-context
kubectl kustomize infra/k8s/overlays/staging
kubectl kustomize infra/k8s/overlays/production
kubectl diff -k infra/k8s/overlays/staging
kubectl diff -k infra/k8s/overlays/production
```

Provision Kubernetes Secrets out of band as described in
`infra/k8s/SECRETS.md`; do not restore a committed Secret manifest.

### Option 3: GitHub Actions + Docker Compose blue-green deployment

The active CI/CD path uses `docker-compose.prod.yml` and
`scripts/deploy-blue-green.sh`:

- A push to `main` builds and publishes immutable `sha-*` backend and
  frontend images. It does **not** deploy automatically. To deploy staging,
  manually dispatch the `CI` workflow on `main` with `deploy_staging=true`.
- A `v*` Git tag builds and publishes matching release-tagged images. After
  CI and security scans pass, the Release workflow publishes the GitHub
  Release. It does **not** deploy production automatically. To deploy,
  manually dispatch `CI` on that `v*` tag with `deploy_production=true`.
- A staging rollback requires a manual CI dispatch on `main` with
  `deploy_staging=true` and a rollback tag (`sha-*` or `v*`). It redeploys that
  selected tag through the same health-check and traffic-switch process; it
  does not blindly retag one image as the other.

Required repository-level Actions secrets and repository variables are listed
in `docs/GITHUB_SECRETS.md`. The target hosts must also have read-only Docker
Hub credentials configured so they can pull the private images. GitHub
Environment branch/tag policies apply to the deploy jobs.

For a manual server-side operation:

```bash
./scripts/deploy-blue-green.sh production v1.2.3
./scripts/deploy-blue-green.sh production v1.2.2 --rollback
```

The rollback command deploys the specified tag to the inactive color, checks
health and smoke tests, and then switches traffic. It requires both backend
and frontend images to exist under that same tag.

See `docs/BLUE_GREEN_DEPLOYMENT.md` for the deployment procedure and
rollback behavior.

## Environment Variables

### Backend (.env)
```env
DATABASE_URL=postgresql://erp:password@postgres:5432/erp_solution
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-256-bit-secret-key
ENVIRONMENT=production
OLLAMA_BASE_URL=http://ollama:11434
CORS_ORIGINS=https://yourdomain.com
JWT_EXPIRE_MINUTES=60
```

### Frontend (.env)
```env
REACT_APP_API_URL=https://api.yourdomain.com
REACT_APP_WS_URL=wss://api.yourdomain.com
REACT_APP_SENTRY_DSN=https://xxx@yyy.ingest.sentry.io/zzz
```

## SSL/TLS Setup

### Let's Encrypt (Free)
```bash
# Using certbot with nginx
certbot --nginx -d yourdomain.com -d api.yourdomain.com
```

### Cloudflare (Recommended)
1. Point DNS to Cloudflare
2. Enable "Full (Strict)" SSL mode
3. Enable Auto Minify, Brotli, HTTP/2

## Monitoring

### Health Checks
- Backend: `GET /health`
- Database: `GET /health/db`
- Redis: `GET /health/redis`

### Prometheus Metrics
- Endpoint: `GET /metrics`
- Metrics: request_count, request_duration, db_connections

### Logging
```python
# Structured logging in production
import structlog
logger = structlog.get_logger()
logger.info("user_login", user_id=123, ip="192.168.1.1")
```

## Backup Strategy

### Database
```bash
# Automated daily backup
pg_dump -h postgres -U erp erp_solution > backup_$(date +%Y%m%d).sql

# Upload to S3
aws s3 cp backup_*.sql s3://your-bucket/backups/
```

### File Storage
- Use S3/MinIO for uploads
- Enable versioning
- Cross-region replication for disaster recovery

## Scaling

### Horizontal Scaling
```yaml
# backend.yaml — scale to 5 replicas
replicas: 5
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

### Database Scaling
- Read replicas for reporting
- Connection pooling (PgBouncer)
- Partitioning for large tables

## Security Checklist

- [ ] Change default passwords
- [ ] Enable 2FA for all admin accounts
- [ ] Set up WAF (Cloudflare/AWS WAF)
- [ ] Regular security audits
- [ ] Dependency scanning (Trivy in CI / Dependabot)
- [ ] Secrets rotation (monthly)
- [ ] Network segmentation (VPC)
- [ ] Backup encryption
- [ ] DDoS protection
- [ ] Rate limiting enabled

## Troubleshooting

### Common Issues

**Database connection failed**
```bash
# Check PostgreSQL is running
docker compose ps
# Check logs
docker compose logs postgres
# Verify credentials
cat backend/.env | grep DATABASE_URL
```

**Frontend can't reach API**
```bash
# Check CORS settings
cat backend/.env | grep CORS
# Verify API is accessible
curl http://localhost:8000/docs
```

**Out of memory**
```bash
# Check memory usage
docker stats
# Increase Docker memory limit
# Or scale down replicas temporarily
```

## Support

- GitHub Issues: https://github.com/nyeinpyaesone-ui/ERP/issues
- Documentation: `/docs` in repository
- API Docs: `https://api.yourdomain.com/docs`
