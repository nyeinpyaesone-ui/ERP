# ERP Solution - Comprehensive Execution Plan
## Build Mode Execution Plan for Production-Ready ERP System

---

## Executive Summary

This plan addresses all identified gaps in the ERP codebase to achieve a production-ready state. The plan is organized into 10 phases covering critical infrastructure, code quality, testing, CI/CD, deployment, monitoring, security, and documentation.

**Current State**: Async/sync fixes committed (6 files), rebase in progress, Docker Compose missing, Alembic 001_initial missing, zero tests, broken CI.

---

## Phase 0: Critical Pre-Flight (Blocking All)
**Priority**: CRITICAL | **Duration**: 2-4 hours | **Dependencies**: None

### Tasks

| ID | Task | Command/Action | Validation | Owner |
|----|------|----------------|------------|-------|
| P0-1 | Install Docker Compose | `sudo apt-get update && apt-get install -y docker-compose-plugin` | `docker compose version` | DevOps |
| P0-2 | Finalize Git Rebase | `git rebase --continue` | `git log --oneline -3` shows clean history | DevOps |
| P0-3 | Start Infrastructure | `docker-compose up -d postgres redis` | `docker-compose ps` shows healthy | DevOps |
| P0-4 | Create Alembic 001_initial | `cd backend && source venv/bin/activate && alembic revision --autogenerate -m "initial schema" && alembic upgrade head` | Migration applies cleanly | Backend |
| P0-5 | Verify Local Build | `cd backend && python -m py_compile app/auth.py app/middleware/tenancy.py app/routers/health.py app/routers/ai.py app/routers/llm.py app/routers/documents.py` | All compile clean | Backend |

### Blockers
- **Docker Compose missing** - Cannot start DB/Redis
- **Alembic 001_initial missing** - Cannot run migrations
- **Git rebase not finalized** - Changes not committed

---

## Phase 1: Async/Sync Mismatch Fixes (Remaining 3 Files)
**Priority**: HIGH | **Duration**: 30 minutes | **Dependencies**: Phase 0 complete

### Remaining Issues (3 files)

| File | Issue | Fix |
|------|-------|-----|
| `backend/app/auth.py:67` | `async def has_permission` calls sync `get_user_permissions` without await | Change to `def has_permission` |
| `backend/app/routers/integrations.py:55` | `async def test_webhook` has 3 sync DB calls | Wrap with `asyncio.to_thread()` |
| `backend/app/routers/payments.py:59` | `async def stripe_webhook` has 3 sync DB calls | Wrap with `asyncio.to_thread()` |

### Implementation
```python
# auth.py:67 - Change to sync
def has_permission(current_user: User, permission_name: str, db: Session) -> bool:
    if current_user.role == "superadmin":
        return True
    user_perms = get_user_permissions(current_user, db)  # No await
    return permission_name in user_perms

# integrations.py:55 - Wrap sync DB calls
async def test_webhook(...):
    webhook = await asyncio.to_thread(lambda: db.query(Webhook).filter(Webhook.id == webhook_id).first())
    ...
    await asyncio.to_thread(lambda: db.add(delivery))
    await asyncio.to_thread(lambda: db.commit())
    await asyncio.to_thread(lambda: db.refresh(delivery))

# payments.py:59 - Wrap sync DB calls
async def stripe_webhook(...):
    invoice = await asyncio.to_thread(lambda: db.query(Invoice).filter(Invoice.id == int(invoice_id)).first())
    ...
    await asyncio.to_thread(lambda: db.add(payment))
    await asyncio.to_thread(lambda: db.commit())
```

### Validation
```bash
cd backend && python -m py_compile app/auth.py app/routers/integrations.py app/routers/payments.py
```

---

## Phase 2: Alembic Migration Infrastructure
**Priority**: HIGH | **Duration**: 2 hours | **Dependencies**: Phase 0-1 complete

### Tasks

| ID | Task | Description |
|----|------|-------------|
| P2-1 | Generate 001_initial | `alembic revision --autogenerate -m "initial schema"` |
| P2-2 | Review Migration | Verify all 27+ models in `models.py` are captured |
| P2-3 | Apply Migration | `alembic upgrade head` |
| P2-4 | Verify Schema | `alembic current` shows head |
| P2-5 | Create Seed Script | `alembic/versions/seed_data.py` for reference data |

### Migration Files Expected
```
backend/alembic/versions/
├── 001_initial_schema.py          # NEW - all 27+ tables
├── 002_add_rbac_permissions.py    # EXISTING
├── 003_add_llm_integration.py     # EXISTING
├── 004_add_elasticsearch_search.py # EXISTING
```

### Validation
```bash
cd backend && alembic upgrade head && alembic current
```

---

## Phase 3: Test Infrastructure (Zero Tests Currently)
**Priority**: HIGH | **Duration**: 8-16 hours | **Dependencies**: Phase 2 complete

### Test Infrastructure to Create

```
backend/tests/
├── conftest.py                 # Async fixtures, test DB, async client
├── pytest.ini                  # Markers, coverage, asyncio config
├── unit/
│   ├── test_auth.py           # JWT, bcrypt, RBAC
│   ├── test_models.py         # 27+ model validations
│   └── test_services.py       # search, llm, permissions, tx
├── integration/
│   ├── test_auth_flow.py      # Login, register, me, refresh
│   ├── test_crm.py            # Companies, contacts, deals
│   ├── test_purchase_orders.py
│   ├── test_ai_llm.py         # Chat, insights, models
│   └── test_integrations.py
├── e2e/
│   └── test_user_journeys.py  # Critical user flows
└── performance/
    └── test_load.py           # k6 or locust scripts
```

### Configuration Files

**pytest.ini**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --strict-markers
    --cov=app
    --cov-report=html
    --cov-report=term-missing
    --asyncio-mode=auto
markers =
    unit: Unit tests
    integration: Integration tests (requires database)
    e2e: End-to-end tests
    slow: Slow running tests
    smoke: Smoke tests for CI
```

**conftest.py** - Async fixtures with test database
```python
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.config import settings

TEST_DATABASE_URL = settings.DATABASE_URL.replace("postgresql", "postgresql+asyncpg").replace("/erp_db", "/erp_test")

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def db_session(test_engine):
    async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

### Coverage Targets

| Layer | Target | Files |
|-------|--------|-------|
| Models | 90% | All 27+ models in `models.py` |
| Services | 85% | `auth.py`, `permissions.py`, `search_service.py`, `llm_service.py` |
| API Routes | 80% | All 27+ routers in `routers/` |
| Utilities | 75% | `config.py`, `database.py`, helpers |

### CI Integration
```yaml
# .github/workflows/ci.yml - test job
test:
  needs: quality
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:15
      env: { POSTGRES_PASSWORD: postgres, POSTGRES_DB: erp_test }
      ports: [5432:5432]
    redis:
      image: redis:7
      ports: [6379:6379]
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: '3.11' }
    - run: pip install -r backend/requirements.txt pytest pytest-cov pytest-asyncio
    - run: cd backend && alembic upgrade head
    - run: cd backend && pytest --cov=app --cov-fail-under=80
```

---

## Phase 4: CI/CD Pipeline Fix
**Priority**: HIGH | **Duration**: 2-4 hours | **Dependencies**: Phase 3 complete

### Current Issues
- CI builds broken `/frontend` (should build `/backend/frontend-react`)
- npm 9 on Node 22 has cache bugs - need npm 10.9.2
- No test step in CI
- Frontend build context wrong

### Required CI Configuration (`.github/workflows/ci.yml`)

```yaml
name: CI
on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r backend/requirements.txt
      - run: cd backend && ruff check . && black --check .
      - run: cd backend && mypy app/

  test:
    needs: quality
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env: { POSTGRES_PASSWORD: postgres, POSTGRES_DB: erp_test }
        ports: [5432:5432]
      redis:
        image: redis:7
        ports: [6379:6379]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r backend/requirements.txt pytest pytest-cov pytest-asyncio
      - run: cd backend && alembic upgrade head
      - run: cd backend && pytest --cov=app --cov-fail-under=80

  frontend:
    needs: quality
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: 
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: backend/frontend-react/package-lock.json
      - run: cd backend/frontend-react && npm ci
      - run: cd backend/frontend-react && npm run build
      - uses: actions/upload-artifact@v4
        with: { name: frontend-dist, path: backend/frontend-react/dist/ }

  docker:
    needs: [test, frontend]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with: { username: ${{ vars.DOCKER_USER }}, password: ${{ secrets.DOCKER_PAT }} }
      - uses: docker/build-push-action@v6
        with:
          context: ./backend
          push: true
          tags: |
            ${{ vars.DOCKER_USER }}/erp-backend:${{ github.sha }}
            ${{ vars.DOCKER_USER }}/erp-backend:latest
          cache-from: type=registry,ref=${{ vars.DOCKER_USER }}/erp-backend:buildcache
          cache-to: type=registry,ref=${{ vars.DOCKER_USER }}/erp-backend:buildcache,mode=max
      - uses: docker/build-push-action@v6
        with:
          context: ./backend/frontend-react
          push: true
          tags: |
            ${{ vars.DOCKER_USER }}/erp-frontend:${{ github.sha }}
            ${{ vars.DOCKER_USER }}/erp-frontend:latest

  security:
    needs: docker
    runs-on: ubuntu-latest
    steps:
      - uses: aquasecurity/trivy-action@master
        with: { image-ref: ${{ vars.DOCKER_USER }}/erp-backend:${{ github.sha }} }
      - uses: aquasecurity/trivy-action@master
        with: { image-ref: ${{ vars.DOCKER_USER }}/erp-frontend:${{ github.sha }} }
```

---

## Phase 5: Production Deployment
**Priority**: HIGH | **Duration**: 4-8 hours | **Dependencies**: Phase 4 complete

### Infrastructure Requirements
| Component | Specification |
|-----------|---------------|
| Server | 4GB RAM, 2 vCPU, 50GB SSD |
| OS | Ubuntu 22.04 LTS |
| Docker | 24+ with Compose plugin |
| SSL | Let's Encrypt via certbot |

### Production Stack (`docker-compose.prod.yml`)
```bash
docker-compose -f docker-compose.prod.yml up -d
# Services:
# - postgres (with pgvector for AI)
# - redis (sessions, cache, rate-limiting)
# - backend (FastAPI, gunicorn/uvicorn workers)
# - frontend (nginx + static + PWA)
# - ollama (GPU preferred, CPU fallback)
# - nginx (SSL termination, rate limit, blue-green routing)
```

### Production Environment (`.env.prod`)
```env
DATABASE_URL=postgresql://user:pass@postgres:5432/erp_prod
REDIS_URL=redis://:pass@redis:6379/0
SECRET_KEY=<64-char-cryptographic>
ENVIRONMENT=production
OLLAMA_BASE_URL=http://ollama:11434
STRIPE_SECRET_KEY=sk_live_***
CORS_ORIGINS=https://app.yourdomain.com
```

### SSL Setup
```bash
# Automated via certbot in nginx container
# Auto-renewal: 0 3 * * * certbot renew --quiet
# Cert paths: /etc/nginx/ssl/fullchain.pem, privkey.pem
```

### Validation
```bash
docker-compose -f docker-compose.prod.yml up -d
curl -f https://yourdomain.com/health && curl -f https://yourdomain.com/ready
```

---

## Phase 6: Blue-Green Deployment
**Priority**: HIGH | **Duration**: 2 hours | **Dependencies**: Phase 5 complete

### Script Validation
```bash
# Existing script: scripts/deploy-blue-green.sh
# Validate and test
./scripts/deploy-blue-green.sh production v1.0.0
./scripts/deploy-blue-green.sh production v1.0.0 --rollback
```

### Deployment Flow
1. Deploy new version to inactive color
2. Smoke test inactive color (`/health`, `/ready`, critical API)
3. Switch nginx upstream
4. Monitor 5 min (error rate < 1%, p95 < 200ms)
4. Decommission old color

### Rollback Procedure
```bash
# Automated rollback on failure
./scripts/deploy-blue-green.sh production PREVIOUS --rollback

# Database rollback if migration failed
cd backend && alembic downgrade -1
```

---

## Phase 7: Monitoring & Observability
**Priority**: MEDIUM | **Duration**: 4-8 hours | **Dependencies**: Phase 5 complete

### Stack
| Component | Tool | Key Metrics |
|-----------|------|-------------|
| Logs | Loki + Grafana | Structured JSON, correlation IDs |
| Metrics | Prometheus + Grafana | p50/p95/p99 latency, error rate, DB pool, Redis hit rate, Ollama queue |
| Alerts | Alertmanager → PagerDuty/Slack | Error rate >1% 5m, DB pool >80%, disk >85%, SSL <14d |
| Tracing | Jaeger (optional) | Request flow, DB query spans |

### Health Endpoints
- `GET /health` - liveness (process alive)
- `GET /ready` - readiness (DB + Redis + Ollama)

### Alerting Rules
```yaml
# Prometheus alerts
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
  for: 5m
  labels: {severity: critical}
  annotations: {summary: "High error rate"}

- alert: DBConnectionPoolHigh
  expr: pg_stat_activity_count / settings.max_connections > 0.8
  for: 2m
  labels: {severity: warning}

- alert: DiskSpaceLow
  expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) < 0.15
  for: 5m
  labels: {severity: warning}
```

---

## Phase 8: Security Hardening
**Priority**: HIGH | **Duration**: 2-4 hours | **Dependencies**: Phase 5 complete

### Security Controls

| Control | Implementation |
|---------|----------------|
| Secrets | GitHub Environments + 1Password CLI |
| Dependencies | Dependabot + Snyk + Trivy in CI |
| Network | VPC, security groups, no public DB, WAF |
| Rate Limit | nginx + Redis sliding window |
| Audit | All admin actions → immutable store |

### Security Checklist
- [ ] Rotate all secrets (JWT secret, Stripe keys, DB passwords)
- [ ] Enable Dependabot alerts
- [ ] Configure Snyk for dependency scanning
- [ ] Add Trivy to CI for container scanning
- [ ] Configure WAF rules (Cloudflare/ModSecurity)
- [ ] Implement rate limiting (nginx + Redis)
- [ ] Enable audit logging for admin actions

---

## Phase 9: Disaster Recovery & Backup
**Priority**: MEDIUM | **Duration**: 2-4 hours | **Dependencies**: Phase 5 complete

### Backup Strategy

| Data | Frequency | Retention | RTO | RPO |
|------|-----------|-----------|-----|-----|
| PostgreSQL | Daily + WAL | 30 days | <15 min | <1 min |
| Redis | RDB every 60s | 7 days | <2 min | <1 min |
| Uploads | Real-time sync | 90 days | <1 hour | <5 min |
| Config/Secrets | On change | Forever | <5 min | 0 |

### Recovery Procedures
```bash
# Database restore
pg_restore -d erp_prod backup.dump

# Full rollback
./scripts/deploy-blue-green.sh production PREVIOUS --rollback
cd backend && alembic downgrade -1

# DR Test (monthly)
./scripts/deploy-blue-green.sh production PREVIOUS --rollback
cd backend && alembic downgrade -1
```

---

## Phase 10: Documentation & Knowledge Transfer
**Priority**: MEDIUM | **Duration**: 4-8 hours | **Dependencies**: All phases complete

### Documentation to Create/Update

| Document | Status | Owner |
|----------|--------|-------|
| `DEPLOYMENT_GUIDE.md` | Complete | DevOps |
| `RUNBOOK.md` | New | DevOps |
| `API_DOCS.md` | Update | Backend |
| `ARCHITECTURE.md` | Update | Architecture |
| `SECURITY.md` | Update | Security |
| `DEVELOPER_ONBOARDING.md` | New | Team Lead |
| `DISASTER_RECOVERY.md` | New | DevOps |

### Runbook Contents
- Deployment procedures
- Rollback procedures
- Incident response playbooks
- Scaling procedures
- Backup/restore procedures
- Security incident response

---

## Decision Points (Require Your Input)

| # | Decision | Options | Recommendation | Status |
|---|----------|---------|----------------|--------|
| 1 | Migration 001_initial | Auto-generate vs Manual | Auto against dev DB | ☐ Pending |
| 2 | Test framework | pytest-asyncio vs pytest | pytest-asyncio | ☐ Pending |
| 3 | Ollama hardware | CPU (g5.xlarge) vs GPU (g4dn.xlarge) | Start CPU, upgrade if >2s | ☐ Pending |
| 4 | Secrets management | GitHub Env + 1Password vs Vault | GitHub Env + 1Password | ☐ Pending |
| 5 | Monitoring | Self-hosted (Prom+Grafana) vs Managed (Datadog) | Self-hosted | ☐ Pending |
| 6 | Frontend hosting | Nginx in Docker vs CDN | Nginx (PWA + API proxy) | ☐ Pending |

---

## Timeline Overview

| Week | Phase | Milestone |
|------|-------|-----------|
| 0 | 0-2 | Pre-flight: Docker, Rebase, DB, Migrations, Async fixes |
| 1 | 3 | Test infrastructure + unit tests (80% coverage) |
| 2 | 3-4 | Integration tests + CI pipeline fix |
| 3 | 4-5 | Frontend CI fixed, Docker build, Staging deploy |
| 4 | 5-6 | Blue-green validated, Production deploy |
| 5 | 6-7 | Monitoring, Security hardening |
| 5 | 8-10 | DR test, Documentation, Knowledge transfer |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Migration failure in prod | Medium | High | Dry-run, instant rollback |
| Ollama latency >5s | High | Medium | Cache responses, fallback |
| Frontend build cache corruption | Medium | Low | Clean build in CI, npm 10 |
| Secrets leak | Low | Critical | GitHub Env, rotation policy |
| DB connection exhaustion | Medium | High | PgBouncer, connection pooling |

---

## Quick Reference: Key Commands

```bash
# Development
make dev                    # docker-compose up -d postgres redis && uvicorn reload

# Test
cd backend && pytest --cov=app --cov-report=html

# Build
docker-compose -f docker-compose.prod.yml build

# Deploy
./scripts/deploy-blue-green.sh production v1.0.0

# Rollback
./scripts/deploy-blue-green.sh production v1.2.2 --rollback

# Logs
docker-compose -f docker-compose.prod.yml logs -f backend

# DB Shell
docker-compose -f docker-compose.prod.yml exec postgres psql -U erp_user erp_db

# Migrate
cd backend && alembic upgrade head

# Backup
pg_dump -Fc erp_prod > backup_$(date +%Y%m%d).dump

# Restore
pg_restore -d erp_prod backup.dump
```

---

## Sign-Off Requirements

| Phase | Sign-Off By | Criteria |
|-------|-------------|----------|
| Phase 0-2 | Backend Lead | All compile, migrations apply, async fixes verified |
| Phase 3 | QA Lead | 80% coverage, all tests pass |
| Phase 4 | DevOps Lead | CI green, Docker builds, security scans pass |
| Phase 5 | DevOps Lead | Staging deploy healthy, all endpoints respond |
| Phase 6 | DevOps Lead | Blue-green deploy/rollback tested |
| Phase 7 | DevOps Lead | Alerts firing, dashboards populated |
| Phase 8 | Security Lead | Audit clean, secrets rotated |
| Phase 9 | DevOps Lead | DR test passed, RTO/RPO met |
| Phase 10 | Team Lead | All docs complete, team trained |

---

## Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Backend Lead | | | |
| DevOps Lead | | | |
| QA Lead | | | |
| Security Lead | | | |
| Team Lead | | | |

---

**Plan Status**: Ready for execution upon decision point confirmations and plan mode exit.