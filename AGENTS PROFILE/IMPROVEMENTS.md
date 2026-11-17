# IMPROVEMENTS — Prioritized System-Improvement Backlog

Scope: **what to improve next, in order**. IDs are referenced from
[MEMORY.md](MEMORY.md) (`T-00x` ↔ `IMP-Px-x`) and routed via
[SKILLS.md](SKILLS.md). Status: ⬜ not started · 🟡 in progress · ✅ done (with evidence).

## P0 — Correctness gates (do first; blocks trustworthy progress)

| ID | Item | Files | Verify |
|----|------|-------|--------|
| ✅ **IMP-P0-1** | Finish & land dirty worktree (MEMORY T-001): `ci.yml`, `permissions_catalogue.py`, 6 test files, `App.jsx`, `pytest.ini`, `pyproject.toml`, lockfile | `.github/workflows/ci.yml`, `backend/app/**`, `backend/frontend-react/src/App.jsx` | **Done 2026-10-04/08:** `bc2e0224` + `b2df79fd`…`80bf5c4a`; worktree clean |
| ⬜ **IMP-P0-2** | Apply migrations **001–008 to live PostgreSQL** (never run; MEMORY T-003) — *blocked: docker daemon needs interactive sudo* | `backend/alembic/versions/` | `docker compose up -d postgres redis` → `alembic upgrade head` → `alembic current` = 008 |
| ✅ **IMP-P0-3** | Fix **AGENTS.md drift** (MEMORY T-002): npm/npx on PATH, Alembic count, test counts, compose v2 | `AGENTS.md` | **Done 2026-10-08:** `80bf5c4a` — no stale claims remain |
| ✅ **IMP-P0-4** | **CI truthfulness**: frontend `lint`/`tsc` steps were `\|\| true` no-ops — removed; real eslint tracked as IMP-P2-5 | `.github/workflows/ci.yml` | **Done 2026-10-08:** `22b44f08` — quality job has only real gates |

## P1 — Hardening & hygiene

| ID | Item | Files | Verify |
|----|------|-------|--------|
| ✅ **IMP-P1-1** | Convert backend Dockerfile to **multi-stage** | `backend/Dockerfile` | **Done:** 2× `FROM … AS builder/runtime` (grep-verified 2026-10-08) |
| ⬜ **IMP-P1-2** | Replace legacy `deploy.sh` with **blue-green** as the only documented path (MEMORY D-004) | `deploy.sh`, `README.md`, `docs/` | Rollback rehearsed: `deploy-blue-green.sh … --rollback` |
| ✅ **IMP-P1-3** | Root hygiene: `package.json` (no scripts, npx-only) removed; `scripts/*.heapsnapshot` ≈233 MB purged | `package.json`, `scripts/` | **Done 2026-10-08:** `du -sh scripts/` = 119K; root package.json deleted (`2a6809bb`) |
| ✅ **IMP-P1-4** | Resolve **broken `/frontend`** tree — `backend/frontend-react` stays canonical (D-001) | `frontend/`, `AGENTS.md` | **Done:** tree gone; docs synced `80bf5c4a` |
| ⬜ **IMP-P1-5** | Production secrets & images (MEMORY T-004): add `DOCKER_USER`, `DOCKER_PAT_BACKEND/FRONTEND`; push both images (currently empty) | GitHub secrets, `docs/GITHUB_SECRETS.md` | Actions `docker-*` jobs green; Hub tags populated |
| ⬜ **IMP-P1-6** | Strengthen test suite toward **80% coverage** (CONTRIBUTING target); currently 58.84% | `backend/app/tests/` | `pytest --cov` trend; no skipped critical paths |
| ⬜ **IMP-P1-7** | Upgrade **SQLAlchemy 2.0.52 → 2.1.x + psycopg3** once a live PostgreSQL exists (2.1 maps `postgresql://` to psycopg — unverifiable offline) | `backend/requirements.txt`, `database.py` | live `alembic upgrade head`; pytest green; pool behavior verified |

## P2 — Platform & roadmap (after P0/P1)

| ID | Item | Reference |
|----|------|-----------|
| ⬜ **IMP-P2-1** | Production server provisioning (MEMORY T-005): `.env.production`, SSL, services up | `docs/END_USER_INSTALL.md`, `docs/PRODUCTION_SETUP.md` |
| ⬜ **IMP-P2-2** | v1.1.0 (Q3 2026): AI forecasting, NL queries, auto reports, anomaly detection, Thai/Vietnamese | `ROADMAP.md`, `CHANGELOG.md` |
| ⬜ **IMP-P2-3** | Verify/repair **mobile** (Expo SDK 50 — marked unverified in AGENTS.md) | `mobile/README.md` |
| ⬜ **IMP-P2-4** | v1.2.0+: offline mobile, barcode/QR, advanced RBAC/audit, multi-currency, BI → v2.0.0 microservices | `ROADMAP.md` |
| ✅ **IMP-P2-5** | Add real **eslint** config + `lint` script for `frontend-react` (replaces the removed CI no-op; IMP-P0-4) | `frontend-react/`, `ci.yml` | **Done 2026-10-08:** `fe239e9f` — 0 errors / 127 warnings, CI enforces |

## Working agreement

1. Pull topmost ⬜/🟡 item whose files you're already touching; never start P2 while a P0 is open.
2. Status changes happen only with Beat C evidence → then append to MEMORY §3.
3. New improvement discovered mid-task → add a row here (with ID), link from MEMORY §4; don't let it live only in chat.
4. PR/commit per item where practical; Conventional Commits; no push unless asked.
