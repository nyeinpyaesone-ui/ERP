# IMPROVEMENTS — Prioritized System-Improvement Backlog

Scope: **what to improve next, in order**. IDs are referenced from
[MEMORY.md](MEMORY.md) (`T-00x` ↔ `IMP-Px-x`) and routed via
[SKILLS.md](SKILLS.md). Status: ⬜ not started · 🟡 in progress · ✅ done (with evidence).

## P0 — Correctness gates (do first; blocks trustworthy progress)

| ID | Item | Files | Verify |
|----|------|-------|--------|
| 🟡 **IMP-P0-1** | Finish & land dirty worktree (MEMORY T-001): `ci.yml`, `permissions_catalogue.py`, 6 test files, `App.jsx`, `pytest.ini`, `pyproject.toml`, lockfile — review diff, run full tests, commit (user-approved) | `.github/workflows/ci.yml`, `backend/app/**`, `backend/frontend-react/src/App.jsx` | `pytest -q` green; `npm run build`; `git status` shows only intended files |
| ⬜ **IMP-P0-2** | Apply migrations **001–006 to live PostgreSQL** (never run; MEMORY T-003) | `backend/alembic/versions/` | `docker-compose up -d postgres redis` → `alembic upgrade head` → `alembic current` = 006 |
| ⬜ **IMP-P0-3** | Fix **AGENTS.md drift** (MEMORY T-002): npm/npx 10.9.2 now on PATH (remove/qualify `npx: not found` pitfalls), Alembic count 001→**006**, confirm `make test` behavior | `AGENTS.md` | `make test` matches documented behavior; no stale claims |
| ⬜ **IMP-P0-4** | **CI truthfulness**: frontend `lint` step is a no-op (no lint config/script); add real lint (`eslint`) *or* drop the step; confirm `make test` works with current PATH | `.github/workflows/ci.yml`, `backend/frontend-react/package.json` | CI job passes and actually fails on lint errors (or step removed) |

## P1 — Hardening & hygiene

| ID | Item | Files | Verify |
|----|------|-------|--------|
| ⬜ **IMP-P1-1** | Convert backend Dockerfile to **multi-stage** (AGENTS.md: currently single-stage) | `backend/Dockerfile` | `docker build` image size ↓; container boots, `/health` OK |
| ⬜ **IMP-P1-2** | Replace legacy `deploy.sh` with **blue-green** as the only documented path (MEMORY D-004) | `deploy.sh`, `README.md`, `docs/` | Rollback rehearsed: `deploy-blue-green.sh … --rollback` |
| ⬜ **IMP-P1-3** | Root hygiene: `package.json` has **no scripts** (only `npx` dep); purge `scripts/*.heapsnapshot` ≈233 MB (MEMORY T-006) | `package.json`, `scripts/` | `npm run`-able or file removed; `du -sh scripts/` sane |
| ⬜ **IMP-P1-4** | Resolve **broken `/frontend`** tree: delete + update references, or quarantine doc — `backend/frontend-react` stays canonical (D-001) | `frontend/`, `AGENTS.md`, CI | No build/doc path references `/frontend` |
| ⬜ **IMP-P1-5** | Production secrets & images (MEMORY T-004): add `DOCKER_USER`, `DOCKER_PAT_BACKEND/FRONTEND`; push both images (currently empty) | GitHub secrets, `docs/GITHUB_SECRETS.md` | Actions `docker-*` jobs green; Hub tags populated |
| ⬜ **IMP-P1-6** | Strengthen test suite toward **80% coverage** (CONTRIBUTING target); currently 3+ unit files inherited | `backend/app/tests/` | `pytest --cov` trend; no skipped critical paths |

## P2 — Platform & roadmap (after P0/P1)

| ID | Item | Reference |
|----|------|-----------|
| ⬜ **IMP-P2-1** | Production server provisioning (MEMORY T-005): `.env.production`, SSL, services up | `docs/END_USER_INSTALL.md`, `docs/PRODUCTION_SETUP.md` |
| ⬜ **IMP-P2-2** | v1.1.0 (Q3 2026): AI forecasting, NL queries, auto reports, anomaly detection, Thai/Vietnamese | `ROADMAP.md`, `CHANGELOG.md` |
| ⬜ **IMP-P2-3** | Verify/repair **mobile** (Expo SDK 50 — marked unverified in AGENTS.md) | `mobile/README.md` |
| ⬜ **IMP-P2-4** | v1.2.0+: offline mobile, barcode/QR, advanced RBAC/audit, multi-currency, BI → v2.0.0 microservices | `ROADMAP.md` |

## Working agreement

1. Pull topmost ⬜/🟡 item whose files you're already touching; never start P2 while a P0 is open.
2. Status changes happen only with Beat C evidence → then append to MEMORY §3.
3. New improvement discovered mid-task → add a row here (with ID), link from MEMORY §4; don't let it live only in chat.
4. PR/commit per item where practical; Conventional Commits; no push unless asked.
