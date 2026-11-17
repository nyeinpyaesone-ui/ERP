# ERP SOLUTION — Agent Instructions

FastAPI backend + Vite/React PWA (canonical frontend) + Expo mobile, deployed by GitHub Actions blue-green.
This file owns **repo facts**. `AGENTS PROFILE/MEMORY.md` (auto-loaded via `opencode.json`) owns **live state and drift** — never duplicate state here.

## Layout & ownership

```
backend/                       # the only backend (FastAPI)
  app/main.py                  # create_app() factory + ROUTER_MOUNTS — the single router registry (20 mounts)
  app/models.py                # ALL 39 SQLAlchemy models (sync Session). Never split without updating alembic/env.py
  app/config.py                # Pydantic Settings; reads ./.env
  app/permissions_catalogue.py # single source of truth: resources, actions, role grants
  app/services/permissions.py  # has_permission / get_user_permissions live ONLY here
  app/routers/ (20) · app/services/ · app/tests/ · alembic/versions/ (001→008)
  pytest.ini                   # the ACTIVE pytest config — see Testing
  frontend-react/              # canonical frontend (see below)
  docker-compose.yml           # nested and UNUSED — the root compose file is the real one
backend/frontend-react/        # the ONLY real frontend (Vite 6 + React 18 PWA)
mobile/                        # Expo app — unverified, no app.json, never built in CI
scripts/lib.sh                 # shared helpers sourced by deploy/backup/rollback scripts
infra/k8s/                     # kustomize base + overlays (not exercised in this environment)
```

- **`backend/frontend-react` is the only frontend.** `/frontend` was deleted (it was broken). Never recreate it, never repoint CI at it.
- Workflows: `ci.yml`, `codeql.yml`, `opencode.yml`, `release.yml`. Every `uses:` is pinned to a 40-char SHA with a `# vX.Y.Z` comment — Dependabot updates those natively. Do not add unpinned actions or reintroduce Snyk (removed; Trivy is the only container scanner).

## Commands

```sh
# Backend — the suite needs no database
cd backend && . venv/bin/activate          # shell is sh: use ".", never "source"
pytest -q                                  # 285 passed, ~35s
coverage run -m pytest -q && coverage report   # 58.89% — the floor (58) lives ONLY in pyproject.toml
ruff check . && black --check .            # clean, 67 files (CI enforces both)
alembic upgrade head --sql                 # offline chain check 001→008, no DB needed
uvicorn app.main:app --reload              # needs postgres + redis reachable
pytest app/tests/unit/test_auth.py -q      # single file
pytest app/tests -k permission -q          # single area

# Frontend
cd backend/frontend-react
npm run dev        # http://localhost:3000, proxies /api → localhost:8000 (ws enabled)
npm test           # vitest run → 105 passed (7 files), ~25s, no backend needed
npm run lint       # eslint src → must stay 0 errors (127 warnings are tolerated)
npm run build      # vite build + PWA service worker
npx vitest run src/api/axios.test.js       # single frontend test

# Repo-wide
make test          # backend pytest + frontend vitest
make lint          # ruff+black (enforced) + mypy (advisory `|| true`) + eslint
make guard         # scripts/repo-guard.sh — run before pushes and after long background jobs
```

Numbers above are the verified baseline (re-verified 2026-10-14). If a count or state differs, investigate rather than assume.

## Runtime gotchas that cost time

- **Docker cannot run on this host.** `/usr/bin/docker` exists but the daemon is unusable (proot/Termux-class aarch64; uid 0 → `newuidmap` fails for rootlesskit and podman). Local DB path = native PostgreSQL/Redis binaries only. Container behaviour is verified by CI, not locally.
- **Two `.env` files must agree.** The backend loads `backend/.env` (relative to CWD); `docker-compose.yml` interpolates `${VAR}` from the **repo-root** `.env`. Keep `SECRET_KEY` identical in both or tokens signed by one are invalid under the other.
- **`ENVIRONMENT` is `Literal["dev","test","prod"]`** — `production`/`development` raise at import. In `prod`, Settings refuses the placeholder `SECRET_KEY`, any key under 32 chars, and the example DB credentials (fail-closed).
- **`backend/static/` is created at import time** by `main.py` before the `StaticFiles` mount. Fresh checkouts lack it — don't remove the `os.makedirs`.
- **The backend container runs `alembic upgrade head` + `python -m app.scripts.seed_defaults` on boot** (`backend/entrypoint.sh`), so schema/seed drift surfaces as a container boot failure, not a test failure.
- **No local DB by default**: the app boots, but DB-backed routes fail until PostgreSQL/Redis are reachable. Tests are unaffected (SQLite in-memory / mocks; `token_store` fails open when Redis is down).
- **npm/npx 10.9.2 are on PATH at `~/.local/bin`** (node at `/usr/bin/node`). `~/.local/bin/npm` is a *shell wrapper* — never invoke it as `node ~/.local/bin/npm`. The Makefile's `NPM` var already falls back to `node /tmp/opencode/npm10/package/bin/npm-cli.js`, which is volatile and may need re-bootstrapping.
- The Postgres MCP server (`scripts/mcp-postgres.sh`) exits 1 unless `POSTGRES_MCP_URL` is exported.

## Testing

- `backend/pytest.ini` is the active config (`pythonpath = .`, `testpaths = app/tests`, `asyncio_mode = auto`). `[tool.pytest.ini_options]` in `pyproject.toml` is **ignored** — edit `pytest.ini`.
- Plain `pytest` does **not** collect coverage (no `--cov` in `addopts`), and a stale `backend/.coverage` under-reports. Always `coverage run -m pytest`.
- CI's Tests job starts `postgres:15` purely for `alembic upgrade head`; Redis is deliberately absent. Markers: `unit`, `integration` (needs DB), `slow`.
- Frontend: mock the API through `src/api/axios`, never `fetch`/`axios` directly — `src/api/single-client.test.js` fails the suite otherwise.

## CI & deploy contract

`ci.yml`: gitleaks → quality (ruff+black enforced, mypy advisory) → tests → {frontend-build, docker-backend, docker-frontend} → security (Trivy, advisory SARIF) → deploy-staging / deploy-production.

- The `config` job publishes `can_push` (DOCKER_USER var + both `DOCKER_PAT_*` secrets) and `can_deploy` (additionally SSH key, both hosts, both `*_KNOWN_HOSTS`). **Deploy jobs skip when these are false — fail-closed by design, not a bug.**
- Trivy consumes the **first line only** of `needs.docker-*.outputs.image_tag` (metadata-action emits one ref per line); `exit-code` is unset, so findings are advisory.
- Deploys SSH to `scripts/deploy-blue-green.sh <env> <version> [--rollback]` (sources `scripts/lib.sh`); root `deploy.sh` is legacy. Staging = pushes to `main`, production = `v*` tags; both require their GitHub environment.
- Pushing needs retry loops here (intermittent GnuTLS failures to github.com); `gh api` usually still works. Commits: Conventional Commits.

## Conventions

- Add a route by appending to `ROUTER_MOUNTS` in `main.py` (the factory and the module-level `app` share the table by construction). Guard it with `require_permission` referencing a **catalogue entry**, or `app/tests/test_permission_consistency.py` fails.
- New permissions: edit `permissions_catalogue.py` only. `has_permission`/`get_user_permissions` must not move back into `auth.py` (that was a circular-import fix).
- Datetimes are tz-aware UTC everywhere — never reintroduce naive `utcnow`.
- Frontend env contract: **only `VITE_API_URL`** is read (default `/api/v1`, same-origin through the nginx/Vite proxy). Do not add `VITE_*` vars without wiring them.
- Frontend is JSX-only: eslint flat config (`eslint.config.js`) + `npm run lint`. There is no tsconfig and no tsc step — don't add one.
- Never hardcode file/test/commit counts in README or STATUS_CHECKLIST — use `git ls-files | wc -l`.

## Where the deep detail lives

- `.opencode/skills/erp-backend`, `erp-frontend`, `erp-ops` — per-area micro-details (router table, single-API-client rule, CI job graph, first-deploy checklist). Load with `@erp-backend` etc. before editing those areas, and keep them in sync when the micro-details change.
- `AGENTS PROFILE/README.md` — the agent profile (MEMORY, SOUL, SUB-AGENTS, TOOLS, HEARTBEATS, SKILLS, IMPROVEMENTS). Only `MEMORY.md` is auto-loaded; read the rest on demand.
- `README.md`, `docs/` (ONBOARDING, API_SUMMARY, BLUE_GREEN_DEPLOYMENT, TROUBLESHOOTING), and `.env.example` — generated from `backend/app/config.py`, so every key there must be a real `Settings` field or an explicit compose interpolation.
