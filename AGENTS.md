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
│   ├── alembic/            # Migrations (001_initial needed, 002-004 exist)
│   ├── Dockerfile          # Single-stage (needs multi-stage)
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
└── .github/workflows/      # CI (build only), CodeQL, Snyk, release
```

## Critical Context

**Two frontends exist:**
- `/backend/frontend-react` — **WORKING**: Vite 6.4.3, React 18, PWA, builds successfully (2068 modules)
- `/frontend` — **BROKEN**: No package.json, no nginx.conf, Dockerfile references missing files
- **CI/CD builds `/frontend`** — will fail. Use `/backend/frontend-react` for any frontend work.

**Database not running** — PostgreSQL/Redis only exist in docker-compose. Backend boots but fails on DB connection (expected). Run `docker-compose up -d postgres redis` first.

**No tests exist** — Zero test files anywhere. `make test` and CI test steps will fail.

**Alembic base migration missing** — Versions 002-004 exist but 001_initial.py needed for current models.

**npm 9 on Node 22 has cache bugs** — Use npm 10.9.2 (downloaded to `/tmp/opencode/npm10/package/bin/npm-cli.js`) for frontend installs.

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

- Python: `ruff`/`black` style (not configured yet), type hints required
- TypeScript: `eslint` + `prettier` (config in `.github/workflows/package.json.devops-snippet.json`)
- Migrations: `alembic revision --autogenerate -m "description"`
- Docker: Multi-stage builds preferred (backend Dockerfile currently single-stage)

## References

- `README.md` — Project overview
- `docker-compose.yml` / `docker-compose.prod.yml` — Service definitions
- `backend/app/main.py` — App wiring, all routers
- `backend/app/models.py` — Complete schema
- `scripts/deploy-blue-green.sh` — New deploy automation
- `.github/workflows/ci.yml` — Current CI (build only)