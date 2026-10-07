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
│   ├── alembic/            # Migrations 001-008 (chain intact; 007-008 reconcile DB to models)
│   ├── Dockerfile          # Multi-stage (builder + runtime AS stages)
│   ├── pytest.ini          # Active pytest config — TAKES PRECEDENCE over pyproject.toml
│   ├── pyproject.toml      # ruff/black/mypy/coverage/isort config
│   ├── requirements.txt    # Pinned to installed versions; local == Docker == CI
│   └── venv/               # Local venv (gitignored)
├── backend/frontend-react/  # WORKING Vite+React PWA — canonical frontend (D-001)
├── mobile/                  # Expo SDK 50 (React Native) - unverified
├── docker-compose.yml       # Dev stack (postgres, redis, backend, frontend, ollama)
├── docker-compose.prod.yml  # Prod stack with nginx, networks, secrets
├── deploy.sh               # Manual SSH deploy (needs blue-green replacement)
├── scripts/                # deploy-blue-green.sh, backup.sh (created during fixes)
├── nginx/                  # nginx.conf, upstream configs (created during fixes)
└── .github/workflows/      # CI (Gitleaks gate, advisory lint), CodeQL, Snyk
```

## Critical Context

**Single canonical frontend:**
- `/backend/frontend-react` — **WORKING**: Vite 6.4.3, React 18, PWA, builds successfully (2068 modules)
- `/frontend` — **deleted** (was broken: no package.json, no nginx.conf). CI builds `backend/frontend-react/dist/`.

**Database not running** — PostgreSQL/Redis only exist in docker-compose. Backend boots but fails on DB connection (expected). Run `docker compose up -d postgres redis` first.

**Tests exist and pass** — `backend/app/tests/` (`unit/` plus top-level files): 285 tests, coverage 58.84%. Run with `make test` or `cd backend && . venv/bin/activate && pytest`. Note `pythonpath` and `testpaths` live in `pytest.ini`, not `pyproject.toml` — pytest.ini wins. CI enforces `--cov-fail-under=58`. No PostgreSQL needed: fixtures use SQLite in-memory or mocks.

**Alembic chain is intact** — 001 through 008. `005` reconciles the permissions table against the catalogue; `007`/`008` bring the migrated schema level with `app/models.py` (verified: all 39 tables, columns and primary keys match). `alembic/env.py` imports `app.models`, so `revision --autogenerate` now works. Still only exercised in offline `--sql` mode — no live PostgreSQL here.

**npm/npx on PATH** — npm/npx 10.9.2 live at `/home/admin/.local/bin` (Node v22.22.1). If a shell still lacks them, fall back to `node /tmp/opencode/npm10/package/bin/npm-cli.js …` (volatile `/tmp` — re-bootstrap if gone).

**Permissions have a single source of truth** — `backend/app/permissions_catalogue.py` defines all resources, actions, and role grants. `has_permission`/`get_user_permissions` live only in `app/services/permissions.py` (removed from `auth.py` to break a circular import). Any router calling `require_permission()` must reference a catalogue entry or `test_permission_consistency.py` fails.

## Key Commands

```bash
# Backend dev (after docker compose up -d postgres redis)
cd backend && source venv/bin/activate && uvicorn app.main:app --reload

# Frontend dev (WORKING portal)
cd backend/frontend-react && node /tmp/opencode/npm10/package/bin/npm-cli.js run dev

# Frontend build (WORKING)
cd backend/frontend-react && node /tmp/opencode/npm10/package/bin/npm-cli.js run build

# Mobile (unverified)
cd mobile && npm install && npx expo start

# Docker dev stack
docker compose up -d postgres redis
docker compose up -d backend frontend

# Docker prod stack
docker compose -f docker-compose.prod.yml up -d

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
| Backend won't start | Start postgres/redis first: `docker compose up -d postgres redis` |
| Alembic "target database not up to date" | Run `alembic upgrade head` or create 001_initial migration |
| CI builds broken frontend | Already fixed — `ci.yml` builds `backend/frontend-react`; do not repoint it |
| Trivy reports no findings | It scanned `sha-<40>` while `metadata-action` pushes `sha-<7>`; `security` now consumes `needs.docker-*.outputs.image_tag` |
| Action version bump needed | Workflows pin `uses:` to a 40-char SHA + `# vX.Y.Z`; Dependabot updates those natively |
| Container runtime won't start here | `/proc/self` reports uid 0 → `newuidmap` fails for rootlesskit/podman; use native PG18 + Redis binaries |
| `npx: not found` in Makefile | npm/npx 10.9.2 should be on PATH (`~/.local/bin`); else use `node /tmp/opencode/npm10/package/bin/npm-cli.js …` |
| pytest `ModuleNotFoundError: app` | `pythonpath` must be in `pytest.ini`; `pyproject.toml` `[tool.pytest.ini_options]` is ignored |
| Postgres MCP queries fail | `POSTGRES_MCP_URL` unset **and** Postgres not running. `export POSTGRES_MCP_URL=...` then `docker compose up -d postgres` |

## Environment Variables

Required for backend (`.env` or docker-compose):
```
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://:pass@host:6379/0
SECRET_KEY=change-in-production
ENVIRONMENT=dev|test|prod
OLLAMA_BASE_URL=http://ollama:11434
STRIPE_SECRET_KEY=sk_...
CORS_ORIGINS=https://app.domain.com
```

## Architecture Notes

- **Auth**: JWT (HS256) access + refresh tokens (rotation, `jti` denylist via `services/token_store.py`), bcrypt passwords, RBAC via `require_admin`, `require_superadmin`, `require_permission` (catalogue-driven)
- **Models**: All in `app/models.py` — User, Company, Contact, Deal, Employee, Product, Invoice, Project, Task, Document, Workflow, Webhook, Integration, ActivityLog, Notification, Report, Forecast, Setting, Role, Permission, SearchIndex, SearchQuery, SearchSuggestion, LLMModel, AIConversation, AIMessage, LLMUsage, AIPromptTemplate
- **Search**: PostgreSQL full-text via `search_service.py`, endpoint `/api/v1/search/`
- **LLM**: Ollama integration via `llm_service.py`, tools, streaming, templates
- **PWA**: Vite plugin generates service worker, offline support
- **Nginx**: Two layers. `backend/frontend-react/nginx.conf` (dev image, port 80) routes `/api` → `backend:8000` with WebSocket upgrade headers and `/` → SPA. `nginx.conf` at the repo root (mounted as `/etc/nginx/nginx.conf` by `docker-compose.prod.yml`) does the same against the blue/green `upstream backend`/`upstream frontend`, includes `nginx/ssl.conf` for TLS, and sets `client_max_body_size 50m` for uploads. The API's WebSocket lives at `/api/v1/ws` — there is no separate `/ws` route.

## File Conventions

- Python: `ruff`/`black` style (configured in `backend/pyproject.toml`), type hints required
- TypeScript: **eslint 10 flat config** (`eslint.config.js`) + `npm run lint` — fails on errors (currently 0 errors / 127 warnings); CI enforces it. No tsc/prettier (JSX project, no tsconfig). The old `.github/workflows/package.json.devops-snippet.json` config was removed with the nested-workflow cleanup.
- Migrations: `alembic revision --autogenerate -m "description"` (works now that `env.py` imports `app.models`; check the generated diff against `Base.metadata` before committing)
- Docker: Multi-stage builds preferred (backend Dockerfile: builder + runtime `AS` stages — already multi-stage)

## OpenCode Config

- `opencode.json` (project) — watcher ignores, permissions, 4 MCP servers
- `~/.config/opencode/opencode.jsonc` (global) — `share: disabled`, compaction, `mcp_timeout`
- MCP servers: `postgres` (via `scripts/mcp-postgres.sh`), `filesystem`, `playwright`, `sequential-thinking`
- `POSTGRES_MCP_URL` must be exported for the Postgres MCP server; wrapper exits 1 if unset

## Agent Profile

Companion profile set in `AGENTS PROFILE/` (identity, memory, coordination —
non-overlapping with this file; see its `README.md` for load order & sync rules):

- `AGENTS PROFILE/MEMORY.md` — durable state: verified snapshot, decisions, open threads, verification ledger (auto-loaded via `opencode.json → instructions`)
- `AGENTS PROFILE/SOUL.md` — identity, values, tone, anti-patterns
- `AGENTS PROFILE/SUB-AGENTS.md` — sub-agent roster & delegation rules
- `AGENTS PROFILE/TOOLS.md` — tool/MCP inventory, permission gates, cheatsheet
- `AGENTS PROFILE/HEARTBEATS.md` — start/edit/done/end checklists & verification gates
- `AGENTS PROFILE/SKILLS.md` — task → skill → verification matrix
- `AGENTS PROFILE/IMPROVEMENTS.md` — prioritized system-improvement backlog (P0–P2)

Rule: **this file owns repo facts**; MEMORY owns live state/drift. Keep facts here,
state there — cross-link, never duplicate.

## References

- `README.md` — Project overview
- `docker-compose.yml` / `docker-compose.prod.yml` — Service definitions
- `backend/app/main.py` — App wiring, all routers
- `backend/app/models.py` — Complete schema
- `backend/app/permissions_catalogue.py` — Permission source of truth
- `scripts/deploy-blue-green.sh` — New deploy automation
- `scripts/mcp-postgres.sh` — Postgres MCP wrapper (reads `POSTGRES_MCP_URL`)
- `.github/workflows/ci.yml` — Current CI (Gitleaks secret gate first; backend ruff+black enforced, mypy advisory; frontend real eslint enforced). All actions SHA-pinned with `concurrency` + `timeout-minutes`.
- `.github/workflows/release.yml` — Tag or manual dispatch → verify pushed images → publish GitHub Release from CHANGELOG.md