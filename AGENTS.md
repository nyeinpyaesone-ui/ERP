# ERP SOLUTION — Agent Instructions

## Repository Structure
```
/home/admin/ERP/
├── backend/                 # FastAPI application (Python 3.11+)
│   ├── app/
│   │   ├── main.py         # App entrypoint, lifespan, router registration
│   │   ├── models.py       # SQLAlchemy models (27+ tables)
│   │   ├── routers/        # 16 API routers (auth, crm, hr, inventory, finance, etc.)
│   │   ├── services/       # Business logic (search, llm, permissions, activity_log)
│   │   ├── database.py     # SQLAlchemy engine/session
│   │   ├── config.py       # Pydantic Settings (.env)
│   │   └── auth.py         # JWT, bcrypt, RBAC dependencies
│   ├── alembic/            # Migrations 001-005 (001_initial exists, chain intact)
│   ├── Dockerfile          # Single-stage (needs multi-stage)
│   ├── pytest.ini          # Active pytest config — TAKES PRECEDENCE over pyproject.toml
│   ├── pyproject.toml      # ruff/black/mypy/coverage/isort config
│   ├── requirements.txt    # Created during fixes
│   └── venv/               # Local venv (gitignored)
├── backend/frontend-react/  # WORKING Vite+React PWA (use this, not /frontend)
├── frontend/                # BROKEN - no package.json, nginx.conf missing
├── mobile/                  # Expo SDK 50 (React Native) - unverified
├── docker-compose.yml       # Dev stack (postgres, redis, backend, frontend, ollama)
├── docker-compose.prod.yml  # Prod stack with nginx, networks, secrets
├── deploy.sh               # Manual SSH deploy (needs blue-green replacement)
├── scripts/                # deploy-blue-green.sh, backup.sh (created during fixes)
├── nginx/                  # nginx.conf, upstream configs (created during fixes)
└── .github/workflows/      # CI (Gitleaks gate, advisory lint), CodeQL, Snyk
```

## Critical Context

**Two frontends exist:**
- `/backend/frontend-react` — **WORKING**: Vite 6.4.3, React 18, PWA, builds successfully (2068 modules)
- `/frontend` — **BROKEN**: No package.json, no nginx.conf, Dockerfile references missing files
- **CI/CD already targets `/backend/frontend-react`** — `.github/workflows/ci.yml` builds `backend/frontend-react/dist/`. The stale `/frontend` warning in older notes is resolved.

**Database not running** — PostgreSQL/Redis only exist in docker-compose. Backend boots but fails on DB connection (expected). Run `docker-compose up -d postgres redis` first.

**Tests exist and pass** — `backend/app/tests/`: `conftest.py`, `test_health.py`, `test_permission_consistency.py` (3 tests). Run with `make test` or `cd backend && . venv/bin/activate && pytest`. Note `pythonpath` lives in `pytest.ini`, not `pyproject.toml` — pytest.ini wins.

**Alembic chain is intact** — 001 through 005. `005_reconcile_permissions.py` reconciles the permissions table against the catalogue. Not yet run against a live PostgreSQL.

**`make test` frontend step fails** — `npx` is not on PATH in this environment (node v22.22.1 is at /usr/bin/node, but npm/npx are absent). Use npm 10.9.2 at `/tmp/opencode/npm10/package/bin/npm-cli.js` for frontend installs and builds.

**Permissions have a single source of truth** — `backend/app/permissions_catalogue.py` defines all resources, actions, and role grants. `has_permission`/`get_user_permissions` live only in `app/services/permissions.py` (removed from `auth.py` to break a circular import). Any router calling `require_permission()` must reference a catalogue entry or `test_permission_consistency.py` fails.

## Key Commands

```bash
# Backend dev (after docker-compose up -d postgres redis)
cd backend && source venv/bin/activate && uvicorn app.main:app --reload

# Frontend dev (WORKING portal)
cd backend/frontend-react && node /tmp/opencode/npm10/package/bin/npm-cli.js run dev

# Frontend build (WORKING)
cd backend/frontend-react && node /tmp/opencode/npm10/package/bin/npm-cli.js run build

# Mobile (unverified)
cd mobile && npm install && npx expo start

# Docker dev stack
docker-compose up -d postgres redis
docker-compose up -d backend frontend

# Docker prod stack
docker-compose -f docker-compose.prod.yml up -d

# Blue-green deploy (NEW)
./scripts/deploy-blue-green.sh production v1.2.3
./scripts/deploy-blue-green.sh production v1.2.2 --rollback

# Alembic (after DB running)
cd backend && source venv/bin/activate && alembic upgrade head
cd backend && source venv/bin/activate && alembic revision --autogenerate -m "initial"
```

## Common Pitfalls

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: psycopg2` | `pip install psycopg2-binary` in venv |
| `npm ENOENT rename` cache errors | Use npm 10: `node /tmp/opencode/npm10/package/bin/npm-cli.js install` |
| Frontend build fails | Use `/backend/frontend-react`, not `/frontend` |
| Backend won't start | Start postgres/redis first: `docker-compose up -d postgres redis` |
| Alembic "target database not up to date" | Run `alembic upgrade head` or create 001_initial migration |
| CI builds broken frontend | Update `.github/workflows/ci.yml` context to `./backend/frontend-react` |
| `npx: not found` in Makefile | npm/npx absent from PATH; use npm 10 at `/tmp/opencode/npm10/package/bin/npm-cli.js` |
| pytest `ModuleNotFoundError: app` | `pythonpath` must be in `pytest.ini`; `pyproject.toml` `[tool.pytest.ini_options]` is ignored |
| Postgres MCP queries fail | `POSTGRES_MCP_URL` unset **and** Postgres not running. `export POSTGRES_MCP_URL=...` then `docker-compose up -d postgres` |

## Environment Variables

Required for backend (`.env` or docker-compose):
```
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://:pass@host:6379/0
SECRET_KEY=change-in-production
ENVIRONMENT=development|production
OLLAMA_BASE_URL=http://ollama:11434
STRIPE_SECRET_KEY=sk_...
CORS_ORIGINS=https://app.domain.com
```

## Architecture Notes

- **Auth**: JWT (HS256), bcrypt passwords, RBAC via `require_admin`, `require_superadmin`, `has_permission`
- **Models**: All in `app/models.py` — User, Company, Contact, Deal, Employee, Product, Invoice, Project, Task, Document, Workflow, Webhook, Integration, ActivityLog, Notification, Report, Forecast, Setting, Role, Permission, SearchIndex, SearchQuery, SearchSuggestion, LLMModel, AIConversation, AIMessage, LLMUsage, AIPromptTemplate
- **Search**: PostgreSQL full-text via `search_service.py`, endpoint `/api/v1/search/`
- **LLM**: Ollama integration via `llm_service.py`, tools, streaming, templates
- **PWA**: Vite plugin generates service worker, offline support
- **Nginx**: Terminates SSL, routes `/api` → backend, `/` → frontend, `/ws` → backend WebSocket

## File Conventions

- Python: `ruff`/`black` style (configured in `backend/pyproject.toml`), type hints required
- TypeScript: no `eslint`/`prettier` config and no `lint` script in `backend/frontend-react/package.json` (CI's `npm run lint || true` is a no-op). The old `.github/workflows/package.json.devops-snippet.json` config was removed with the nested-workflow cleanup.
- Migrations: `alembic revision --autogenerate -m "description"`
- Docker: Multi-stage builds preferred (backend Dockerfile currently single-stage)

## OpenCode Config

- `opencode.json` (project) — watcher ignores, permissions, 4 MCP servers
- `~/.config/opencode/opencode.jsonc` (global) — `share: disabled`, compaction, `mcp_timeout`
- MCP servers: `postgres` (via `scripts/mcp-postgres.sh`), `filesystem`, `playwright`, `sequential-thinking`
- `POSTGRES_MCP_URL` must be exported for the Postgres MCP server; wrapper exits 1 if unset

## References

- `README.md` — Project overview
- `docker-compose.yml` / `docker-compose.prod.yml` — Service definitions
- `backend/app/main.py` — App wiring, all routers
- `backend/app/models.py` — Complete schema
- `backend/app/permissions_catalogue.py` — Permission source of truth
- `scripts/deploy-blue-green.sh` — New deploy automation
- `scripts/mcp-postgres.sh` — Postgres MCP wrapper (reads `POSTGRES_MCP_URL`)
- `.github/workflows/ci.yml` — Current CI (Gitleaks secret gate first, advisory lint)