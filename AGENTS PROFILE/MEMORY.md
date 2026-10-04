# MEMORY — ERP SOLUTION Agent Memory

Durable cross-session state. Companion to [`AGENTS.md`](../AGENTS.md)
(AGENTS.md = **how the repo works**; this file = **what is true right now**).
Append-only ledger; never store secrets (env var *names* only).

**Last verified:** 2026-10-03 (session: agent-memory-profile creation)

---

## 1. Verified snapshot

| Fact | Value | Source |
|------|-------|--------|
| Git HEAD | `328ad9d7` "chore: consolidate pycache ignores, track .dockerignore files" | `git log` |
| Worktree | **Dirty** — ≥12 modified files (see §4) | `git status --short` |
| Node | v22.22.1 at `/usr/bin/node` | `node --version` |
| npm / npx | **10.9.2 NOW ON PATH** at `/home/admin/.local/bin` | `which npm npx` |
| npm fallback | `/tmp/opencode/npm10/package/bin/npm-cli.js` still exists (volatile `/tmp` — re-bootstrap if gone) | `ls` |
| Python | 3.14.4 system; `backend/venv/` present (alembic, black, celery in bin) | `python3 --version`, `ls venv/bin` |
| Alembic chain | **001 → 006** (`006_inventory_payment_setting_columns.py` added) | `ls alembic/versions/` |
| Frontend (canonical) | `backend/frontend-react` — scripts: `dev`, `build`, `preview`, `test` (vitest), `test:watch` | `package.json` |
| CI workflows | `ci.yml`, `codeql.yml`, `snyk-container.yml` | `ls .github/workflows` |
| Profile files | No pre-existing AGENTS PROFILE/memory.md before 2026-10-03 | `find -iname` |

## 2. Decisions ledger

| ID | Decision | Rationale / hook |
|----|----------|------------------|
| D-001 | **`backend/frontend-react` is the only real frontend**; `/frontend` is broken and deprecation-only | AGENTS.md Critical Context; CI builds `backend/frontend-react/dist/` |
| D-002 | Permissions single source of truth = `backend/app/permissions_catalogue.py`; `has_permission` lives only in `app/services/permissions.py` | Broke circular import; `test_permission_consistency.py` enforces |
| D-003 | `backend/pytest.ini` wins over `pyproject.toml` for pytest config (`pythonpath`) | Active config precedence |
| D-004 | Blue-green (`scripts/deploy-blue-green.sh`) is the deploy path; root `deploy.sh` is legacy pending replacement | IMP-P1-2 |
| D-005 | Profile load path = `AGENTS.md` + `AGENTS PROFILE/MEMORY.md` only; other profile files on demand | Context economy; see `README.md → Load order` |
| D-006 | Commit style = Conventional Commits (`feat:`/`fix:`/`docs:`/…) | CONTRIBUTING.md |

## 3. Progress log

- **Done (repo history):** permissions catalogue + RBAC tests + migrations 005–006 +
  CI/deploy hardening (`c4f512ed`); pycache/dockerignore consolidation (`328ad9d7`);
  blue-green deploy + backup scripts + nginx configs created (per AGENTS.md).
- **Done (this session):** created `AGENTS PROFILE/` with README, MEMORY, SOUL,
  SUB-AGENTS, TOOLS, HEARTBEATS, SKILLS, IMPROVEMENTS; cross-linked from AGENTS.md.
- **Verified this session:** §1 table, `make test` NOT run, `pytest` NOT run,
  frontend build NOT run (honest ledger — see §5).
- **Done (2026-10-03 E2E):** 7-agent parallel inspect (backend 256 passed, frontend 60/60 + build green, infra config-valid, docs drift tabled, mobile/knowledge gaps filed, hygiene: v1.1.0=22046 polluted, HEAD clean). Implemented: RELEASE appendix + README/CHANGELOG count fixes + `.gitignore` hardening + PWA icons (192/512, in dist/) + `docs/API_SUMMARY.md` regen from live OpenAPI (98 paths, 150 refs). Validated: pytest 256 passed, ruff/black clean, `/health`+`/docs` 200. NOT done (needs approval): `tag -d list`, v1.1.1 re-cut, commit/push.
- **Done (2026-10-03 finish-all):** remaining doc gaps fixed (mobile RN 0.86.0,
  knowledge 18/24 + routes-planned, integration skeleton note, STATUS counts).
  Committed `6657707e` (11 files, Conventional Commit; pre-existing dirty
  AGENTS.md/entrypoint.sh/opencode.json + untracked AGENTS PROFILE/ left out).
  Deleted stray local tag `list`; cut annotated `v1.1.1` on 6657707e (261 files,
  clean — 0 node_modules/pyc). Push BLOCKED: no network (DNS/TLS fail to
  github.com) — `git push origin main --tags` must be retried with connectivity.
  Post-commit validation: pytest 256 passed, ruff clean.
- **Done (resume):** network restored — `git push origin main --tags` succeeded;
  `main` in sync with `origin/main`, `v1.1.1` live on remote. Remote has no
  `list` tag (nothing to delete remotely). Note: GitHub reports 106 Dependabot
  vulnerabilities on default branch (9 critical) — follow-up work, out of scope.
- **Done (dep hardening):** pip-audit found ecdsa/Minerva (via python-jose, no
  fix); swapped python-jose→PyJWT 2.15.1 (HS256-compatible) — pip-audit clean.
  Frontend `npm audit fix`: 14→11 vulns (rest need breaking majors, deferred).
  Mobile: no lockfile, lock-only resolve fails on Expo peers — left pinned.
  Committed `7f21f48f` (4 files) + pushed to origin/main. Validated: pytest 256,
  ruff/black, vitest 60/60, vite build green.

## 4. Open threads

| ID | Thread | Next action |
|----|--------|-------------|
| T-001 | **Uncommitted work**: `ci.yml`, `permissions_catalogue.py`, 6 test files, `frontend-react/src/App.jsx`, `pytest.ini`, `pyproject.toml`, lockfile modified | Review diff → run tests → commit with Conventional Commit (only if user asks) |
| T-002 | **Drift vs AGENTS.md**: (a) "npx absent" — now false, npm 10.9.2 on PATH; (b) "Alembic 001-005" — now 001-006 | Correct AGENTS.md after confirming `make test` behavior with new PATH |
| T-003 | Alembic 001-006 **never applied to live PostgreSQL** | `docker-compose up -d postgres redis` → `alembic upgrade head` |
| T-004 | GitHub secrets pending: `DOCKER_USER`, `DOCKER_PAT_BACKEND`, `DOCKER_PAT_FRONTEND`; Docker Hub images empty | STATUS_CHECKLIST.md → docs/GITHUB_SECRETS.md |
| T-005 | Production server not provisioned (`.env.production`, services) | docs/END_USER_INSTALL.md |
| T-006 | Root `package.json` has **no scripts**, only dep `npx@10.2.2` (odd); `scripts/*.heapsnapshot` ≈233 MB present (gitignored) | Cleanup task IMP-P1-3 |

## 5. Verification ledger

| Check | Result | When |
|-------|--------|------|
| `pytest` (backend) | ⬜ not run this session | — |
| `backend/frontend-react` build | ⬜ not run this session | — |
| `alembic upgrade head` vs live DB | ⬜ not run (DB down) | — |
| File/dir existence checks (§1) | ✅ via `ls`/`git`/`node -e` | 2026-10-03 |
| Prior-session claim: 3 backend tests pass | ⏳ inherited from AGENTS.md, re-verify before trusting | — |

> Rule: mark ⬜/⏳ honestly. Never upgrade a claim to ✅ without tool output.

## 6. Environment & config pointers

- Required env **names** (values in `.env`, never here): `DATABASE_URL`, `REDIS_URL`,
  `SECRET_KEY`, `ENVIRONMENT`, `OLLAMA_BASE_URL`, `STRIPE_SECRET_KEY`, `CORS_ORIGINS`,
  `POSTGRES_MCP_URL` (MCP only).
- Services must be up first: `docker-compose up -d postgres redis`.
- OpenCode: project `opencode.json` (permissions, watcher ignores, 4 MCP servers);
  global `~/.config/opencode/opencode.jsonc`.
- MCP: `postgres` (`scripts/mcp-postgres.sh`, exits 1 if `POSTGRES_MCP_URL` unset),
  `filesystem` (scoped to `/home/admin/ERP/backend`), `playwright`,
  `sequential-thinking`.

## 7. Amnesia rules (how to rebuild context fast)

1. Read `AGENTS.md` → `MEMORY.md` §1/§4/§5 (this file) → `git status` + `git log -5`.
2. Trust §1 only after re-running its source commands — hardware and PATH change.
3. Any statement older than the last merge to `main` → re-verify before acting.
4. On forgetting a decision: check §2 first; if absent, it was never a decision.
5. Session end: append to §3, update §5 with actual results, add drift to §4.
