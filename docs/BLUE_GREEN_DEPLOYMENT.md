# Blue-Green Deployment Guide

This guide covers zero-downtime production deployments using the `deploy-blue-green.sh` script.

---

## Concept

```
┌─────────────────────────────────────────────────────────────────┐
│                        NGINX (Traffic Router)                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  upstream-active.conf  ──symlink──►  upstream-blue.conf  │   │
│  │                          (LIVE TRAFFIC)                   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
    ┌─────────────────────┐         ┌─────────────────────┐
    │    BLUE ENVIRONMENT │         │   GREEN ENVIRONMENT │
    │  (Currently Active) │         │   (Staging/Next)    │
    │                     │         │                     │
    │ erp-blue-backend    │         │ erp-green-backend   │
    │ erp-blue-frontend   │         │ erp-green-frontend  │
    │                     │         │                     │
    │ Shared: PostgreSQL, Redis, Ollama, Nginx             │
    └─────────────────────┘         └─────────────────────┘
```

**Key Principle:** Only **one** environment receives live traffic at a time. The inactive environment is fully started and health-checked **before** traffic switches.

---

## Prerequisites

- ✅ Initial installation complete (`install.sh` run successfully)
- ✅ Blue environment running and healthy
- ✅ Docker images built/pushed for new version (or using `latest`)
- ✅ Access to production server via SSH

---

## Deploy New Version

### Basic Deploy
```bash
# On production server
cd /opt/erp-solution  # or wherever repo is cloned
./scripts/deploy-blue-green.sh production v1.2.3
```

### What Happens (Step-by-Step)

| Step | Action | Duration | Failure Behavior |
|------|--------|----------|------------------|
| 1 | Load `/opt/erp-solution/.env.production` | <1s | Exit if missing |
| 2 | Validate environment | <1s | Exit on invalid config |
| 3 | Pull images for **inactive** color | 30-120s | Retry/pull error → exit |
| 4 | Start inactive backend + frontend | 10-30s | Container start error → exit |
| 5 | Wait for health checks | 30-300s | Timeout → stop inactive, exit |
| 6 | Run smoke tests (health/ready/root) | 5-15s | Any fail → stop inactive, exit |
| 7 | **Atomic traffic switch** (nginx symlink + reload) | <5s | Rollback to old, exit |
| 8 | Post-switch smoke tests | 5-10s | Fail → rollback traffic, exit |
| 9 | Stop old environment | 5-10s | Warning only (old still accessible) |

**Total typical time:** 2-5 minutes

### Version Tagging Strategy

| Tag Format | Example | Use Case |
|------------|---------|----------|
| Semantic | `v1.2.3` | Production releases |
| Date-based | `v2024.01.15` | Daily builds |
| Git SHA | `sha-a1b2c3d` | Hotfixes, debugging |
| `latest` | `latest` | **Not recommended** for production |

> **Best Practice:** Always tag releases in Git and use that tag:
> ```bash
> git tag v1.2.3
> git push origin v1.2.3
> # CI builds images tagged v1.2.3
> ./scripts/deploy-blue-green.sh production v1.2.3
> ```

---

## Rollback

### Automatic Rollback (Post-Deploy Failure)
If smoke tests fail **after** traffic switch, the script automatically:
1. Switches traffic back to previous color
2. Stops the failed environment
3. Exits with error

### Manual Rollback
```bash
# Rollback to previous version (stored in .previous_version)
./scripts/deploy-blue-green.sh production v1.2.2 --rollback
```

**What happens:**
1. Reads `.previous_version` file (e.g., `v1.2.2`)
2. Identifies current active color (e.g., `green`)
3. Switches traffic to inactive color (e.g., `blue`) which runs `v1.2.2`
4. Stops the failed environment (`green` running `v1.2.3`)

> **Note:** Rollback only works if the previous version's containers still exist (they're stopped, not removed). After a successful deploy, the old environment is stopped but preserved for rollback.

---

## Smoke Tests Explained

The script runs these tests **inside the backend container** before and after traffic switch:

| Test | Endpoint | Expected | Purpose |
|------|----------|----------|---------|
| Health | `GET /api/v1/health` | `200 OK`, `{"status":"healthy"}` | Basic liveness |
| Readiness | `GET /api/v1/ready` | `200 OK`, `{"status":"ready","checks":{...}}` | DB/Redis connectivity |
| API Root | `GET /` | `200 OK` | Router mounted |

**Customizing:** Edit `run_smoke_tests()` in `deploy-blue-green.sh` to add more checks (e.g., `/api/v1/users`, database query).

---

## Troubleshooting

### Deployment Stuck at "Waiting for health"
```bash
# Check container status
docker ps -a --filter "name=erp-green"

# Check backend logs
docker logs erp-green-backend-1 --tail 100

# Common causes:
# - DATABASE_URL points to wrong host
# - SECRET_KEY mismatch
# - Migration pending (run: docker-compose run --rm backend alembic upgrade head)
# - Port 8000 already in use
```

### Smoke Tests Fail
```bash
# Test manually from inside container
docker exec erp-green-backend-1 curl -sf http://localhost:8000/api/v1/health
docker exec erp-green-backend-1 curl -sf http://localhost:8000/api/v1/ready
docker exec erp-green-backend-1 curl -sf http://localhost:8000/

# Check nginx config
docker exec erp-nginx cat /etc/nginx/conf.d/upstream-active.conf
# Should show upstream-green.conf or upstream-blue.conf
```

### Traffic Switch Failed
```bash
# Check nginx syntax
docker exec erp-nginx nginx -t

# Check nginx error logs
docker exec erp-nginx tail -50 /var/log/nginx/error.log

# Manual traffic switch (emergency)
docker exec erp-nginx ln -sf /etc/nginx/conf.d/upstream-blue.conf /etc/nginx/conf.d/upstream-active.conf
docker exec erp-nginx nginx -s reload
```

### Rollback Failed
```bash
# Check .previous_version exists
cat /opt/erp-solution/.previous_version

# Check active color
cat /opt/erp-solution/.active_color

# Manual rollback
docker exec erp-nginx ln -sf /etc/nginx/conf.d/upstream-blue.conf /etc/nginx/conf.d/upstream-active.conf
docker exec erp-nginx nginx -s reload
echo "blue" > /opt/erp-solution/.active_color
```

---

## Monitoring Deployment

### Log File
Each deployment creates a timestamped log:
```bash
# Latest deployment log
ls -lt /opt/erp-solution/logs/deploy-*.log | head -1

# Follow in real-time
tail -f /opt/erp-solution/logs/deploy-$(date +%Y%m%d)*.log
```

### Key Log Messages
| Message | Meaning |
|---------|---------|
| `Pulling images for production-green` | Starting image pull |
| `green environment is healthy` | Health checks passed |
| `Smoke tests passed for green environment` | Pre-switch tests OK |
| `Traffic switched to green` | **Live traffic now on green** |
| `Post-switch smoke tests passed` | External verification OK |
| `Old blue environment stopped` | Cleanup complete |

---

## Advanced Usage

### Deploy to Staging First
```bash
# Deploy to staging environment (separate server or namespace)
./scripts/deploy-blue-green.sh staging v1.2.3

# After verification, promote to production
./scripts/deploy-blue-green.sh production v1.2.3
```

### Deploy Specific Services Only
```bash
# The script only deploys backend + frontend (shared services stay running)
# To update shared services, use docker-compose directly:
docker-compose -f docker-compose.prod.yml pull postgres redis ollama
docker-compose -f docker-compose.prod.yml up -d postgres redis ollama
```

### Emergency Hotfix (Skip Version Tag)
```bash
# If you must deploy uncommitted changes (not recommended)
./scripts/deploy-blue-green.sh production latest
# Uses whatever 'latest' tag points to on Docker Hub
```

### Dry Run (Check What Would Happen)
```bash
# No dry-run flag exists, but you can trace:
bash -x ./scripts/deploy-blue-green.sh production v1.2.3 2>&1 | head -50
```

---

## File Reference

| File | Purpose |
|------|---------|
| `scripts/deploy-blue-green.sh` | Main deployment script |
| `/opt/erp-solution/.active_color` | Current active color (blue/green) |
| `/opt/erp-solution/.previous_version` | Last deployed version for rollback |
| `/opt/erp-solution/logs/deploy-*.log` | Deployment logs |
| `nginx/upstream-blue.conf` | Blue upstream definition (backend:8000, frontend:3000) |
| `nginx/upstream-green.conf` | Green upstream definition (erp-green-backend:8000, erp-green-frontend:3000) |
| `nginx/upstream-active.conf` | Symlink to active upstream |
| `docker-compose.prod.yml` | Service definitions (blue + green profiles) |

---

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| Shared PostgreSQL/Redis | Avoids data sync complexity; migrations run once |
| Nginx symlink switch | Atomic, no connection drops, sub-second |
| Health checks in container | Tests actual service, not just port |
| Smoke tests pre + post switch | Catches config issues before/after traffic |
| Preserve old env for rollback | Instant rollback without rebuild |

---

## Best Practices Checklist

- [ ] Tag release in Git (`git tag v1.2.3 && git push origin v1.2.3`)
- [ ] Verify CI built images for that tag (`powerrangeranikg/erp-solution-backend:v1.2.3`)
- [ ] Run during low-traffic window
- [ ] Monitor deployment log in real-time
- [ ] Verify post-deploy: API health, frontend loads, key user flows
- [ ] Keep previous version for 24h before cleanup
- [ ] Document any issues in deployment log

---

## Related Documentation

| Document | Link |
|----------|------|
| End-User Install | `docs/END_USER_INSTALL.md` |
| Backup & Restore | `docs/BACKUP_RESTORE.md` |
| Disaster Recovery | `docs/DISASTER_RECOVERY.md` |
| Operations Runbook | `docs/OPERATIONS_RUNBOOK.md` |
| Production Deployment | `docs/PRODUCTION_DEPLOYMENT.md` |