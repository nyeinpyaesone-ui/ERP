---
name: ERP Backend
description: FastAPI backend micro-details for /home/admin/ERP/backend - app factory, 21 router mounts, auth/RBAC, permissions catalogue, migrations, and the exact test/lint/coverage battery with expected results and known pitfalls
---

# ERP Backend (FastAPI, sync SQLAlchemy)

Work on `backend/` only with this loaded. Paths are relative to the repo root.

## Layout & ownership

- `app/main.py` — `create_app(settings_override, mounts)` factory (Twelve-Factor). `settings_override` accepts a `Settings` instance or dict; `mounts` swaps the router table for narrow test boots. `app = create_app()` is the module-level app uvicorn serves.
- `app/models.py` — ALL 27+ SQLAlchemy models (sync `Session`, 2.0-style `DeclarativeBase`). Never split models without updating alembic env imports.
- `app/config.py` — Pydantic `Settings` with `extra="ignore"`. `ENVIRONMENT` is `Literal["dev","test","prod"]` — `production` RAISES AT IMPORT (never write it, D-014).
- `app/permissions_catalogue.py` — single source of truth for resources/actions/role grants. `has_permission`/`get_user_permissions` live ONLY in `app/services/permissions.py` (circular-import fix, D-002).
- `app/auth.py` — JWT HS256 access+refresh with rotation and `jti` denylist (`services/token_store.py`, fails open if Redis down). Guards: `require_admin`, `require_superadmin`, `require_permission` (catalogue-driven).

## Router mounts (ROUTE_MOUNTS table in main.py — the only registry)

| Prefix | Module | Prefix | Module |
|---|---|---|---|
| /api/v1/auth | auth | /api/v1/payments | payments (Stripe, fail-closed 400) |
| /api/v1/crm | crm | /api/v1/integrations | integrations |
| /api/v1/hr | hr | /api/v1/analytics | analytics |
| /api/v1/inventory | inventory | /api/v1/admin | admin |
| /api/v1/finance | finance | /api/v1/ws | websocket (WS — the only one) |
| /api/v1/projects | projects | /api/v1/search | search (PG full-text) |
| /api/v1/ai | ai | /api/v1/permissions | permissions |
| /api/v1/documents | documents | /api/v1/llm | llm (Ollama, 10/120s httpx) |
| /api/v1/reports | reports | /api/v1 | health |
| /api/v1/workflows | workflows | "" | health_root (/health, /ready) |

Adding a route: append to `ROUTER_MOUNTS` (factory and module app share it by construction), guard with `require_permission` referencing a catalogue entry or `test_permission_consistency.py` fails.

## Commands (from `backend/`; shell is `sh` — use `.`, never `source`)

```sh
. venv/bin/activate
pytest -q                       # 285 passed, 6 warnings (~30s), no DB needed
coverage run -m pytest -q && coverage report   # 58.89%, floor 58 in pyproject (D-010)
ruff check . && black --check . # clean, 67 files
alembic upgrade head --sql      # offline chain check 001->008
alembic revision --autogenerate -m "..."       # works (env.py imports app.models)
uvicorn app.main:app --reload   # needs postgres/redis via docker compose first
```

## Pitfalls

- pytest config lives in `pytest.ini` (pythonpath=.); `pyproject.toml` [tool.pytest.ini_options] is IGNORED (D-003).
- Plain `pytest` does NOT run coverage (no --cov in addopts); a stale `.coverage` file can under-report — always `coverage run -m pytest`.
- Fresh checkouts lack `backend/static/`; main.py makedirs it before StaticFiles mount (59156a96) — don't remove that.
- `psycopg2` missing → `pip install psycopg2-binary`; DB absent → backend boots but DB routes fail (expected locally; CI has postgres:15).
- Datetimes are tz-aware UTC everywhere (2a6809bb); never reintroduce naive `utcnow`.
