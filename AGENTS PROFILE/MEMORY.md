# MEMORY — ERP SOLUTION Agent Memory

Durable cross-session state. Companion to [`AGENTS.md`](../AGENTS.md)
(AGENTS.md = **how the repo works**; this file = **what is true right now**).
Append-only ledger; never store secrets (env var *names* only).

**Last verified:** 2026-10-08 (session: fix-everything sweep + B1 single-client)

---

## 1. Verified snapshot

| Fact | Value | Source |
|------|-------|--------|
| Git HEAD | `80bf5c4a` docs sync; session landed `b2df79fd`→`7014a496` + docs (run `git log -10`) | `git log` |
| Worktree | **Clean** (after this session's commit series) | `git status --short` |
| Node | v22.22.1 at `/usr/bin/node` | `node --version` |
| npm / npx | **10.9.2 on PATH** at `/home/admin/.local/bin` | `which npm npx` |
| npm fallback | `/tmp/opencode/npm10/…` volatile — re-bootstrap if gone | `ls` |
| Python | 3.14.4 (venv) — runs 285 tests; Docker image is 3.11-slim | `python --version` |
| Alembic chain | **001 → 008** (offline `--sql` regenerates 47 DDL stmts under alembic 1.20) | `alembic upgrade head --sql` |
| Frontend (canonical) | `backend/frontend-react` — scripts: `dev`, `build`, `preview`, `test`, `test:watch`; **105 vitest tests** | `package.json`, `npm run test` |
| CI workflows | `ci.yml`, `codeql.yml`, `opencode.yml`, `snyk-container.yml` | `ls .github/workflows` |
| Docker daemon | **Down** — `docker compose` v2.40.3 present, but socket missing; start needs interactive sudo | `docker ps` |
| gh CLI | Installed, **not authenticated** — secrets/PR operations unavailable | `gh auth status` |

## 2. Decisions ledger

| ID | Decision | Rationale / hook |
|----|----------|------------------|
| D-001 | **`backend/frontend-react` is the only real frontend**; `/frontend` is broken and deprecation-only | AGENTS.md Critical Context; CI builds `backend/frontend-react/dist/` |
| D-002 | Permissions single source of truth = `backend/app/permissions_catalogue.py`; `has_permission` lives only in `app/services/permissions.py` | Broke circular import; `test_permission_consistency.py` enforces |
| D-003 | `backend/pytest.ini` wins over `pyproject.toml` for pytest config (`pythonpath`) | Active config precedence |
| D-004 | Blue-green (`scripts/deploy-blue-green.sh`) is the deploy path; root `deploy.sh` is legacy pending replacement | IMP-P1-2 |
| D-005 | Profile load path = `AGENTS.md` + `AGENTS PROFILE/MEMORY.md` only; other profile files on demand | Context economy; see `README.md → Load order` |
| D-006 | Commit style = Conventional Commits (`feat:`/`fix:`/`docs:`/…) | CONTRIBUTING.md |
| D-007 | **SQLAlchemy pinned 2.0.52** until a live PostgreSQL can verify the 2.1 psycopg3 path | IMP-P1-7; 2.1 `postgresql://`→psycopg unverifiable with docker daemon down |
| D-008 | **Single API client**: pages/contexts must use `src/api/axios`; enforced by `single-client.test.js` (twin of backend AST gate) | B1; tokens/401 handling live only in the interceptor |

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
- **Done (2026-10-04 INT-1 + Slice A):** docs/profile tracked `bc2e0224`;
  A1 twelve-factory config + `create_app` factory `b2df79fd`; A2 refresh-token
  rotation + jti denylist + auth schemas `26363420`; A3 `require_permission`
  over projects/ai/reports/analytics/integrations + AST gate `01c60370`
  (256→285 tests, coverage 58.84%).
- **Done (2026-10-08 fix-everything sweep):** datetime.utcnow/local-now →
  tz-aware UTC across 13 files (`2a6809bb`, 0 deprecation warnings — note: this
  commit also swept the staged root `package.json` deletion); deps fastapi
  0.142.2/starlette 1.7.0/alembic 1.20/black 26.10/dotenv 1.2.4/httpx2 2.13.1
  + `declarative_base` 2.0-style (`0a9326cf`); CI no-op lint+tsc removed
  (`22b44f08`); frontend lockfile audit-fix + vite 6.4.4 (`b6b079c3`); **B1
  single-client migration** 16 files + enforcement test (`7014a496`, vitest
  105/105 + build); AGENTS.md facts synced (`80bf5c4a`). Hygiene: 223MB
  heapsnapshots purged (scripts/ = 119K), stale stash@{0} triaged & dropped
  (all hunks superseded; mobile-ci templates noted for IMP-P2-3), backend/.env
  created from example with random SECRET_KEY (gitignored). SQLAlchemy 2.1
  upgrade attempted → reverted (D-007). **Not pushed** (ask-gate).

## 4. Open threads

| ID | Thread | Next action |
|----|--------|-------------|
| T-003 | Alembic 001–008 **never applied to live PostgreSQL** — blocked: docker daemon down, start needs interactive sudo | `sudo systemctl start docker` → `docker compose up -d postgres redis` → `alembic upgrade head` |
| T-004 | GitHub secrets pending: `DOCKER_USER`, `DOCKER_PAT_BACKEND/FRONTEND`; Docker Hub images empty; `gh` unauthenticated | `gh auth login` → STATUS_CHECKLIST.md → docs/GITHUB_SECRETS.md |
| T-005 | Production server not provisioned (`.env.production`, services) | docs/END_USER_INSTALL.md |
| T-007 | **Commits not pushed**: `bc2e0224`…`80bf5c4a` + docs sync local only; 37 Dependabot branches on remote | `git push origin main` when asked |
| T-008 | GitHub reports 106 Dependabot vulnerabilities (9 critical) on default branch | Dependabot PR triage; batch mobile ones with MAP-6 |
| T-009 | Frontend 2 moderate prod vulns remain — need breaking majors (react 19 / router 7 / tailwind 4) | batch upgrade epic after B1 |
| T-010 | `backend/.env` created (random SECRET_KEY, gitignored) — local dev only; Docker/CI use their own env | none (informational) |

## 5. Verification ledger

| Check | Result | When |
|-------|--------|------|
| `pytest` (backend) | ✅ 285 passed, 6 warnings, 0 deprecations | 2026-10-08 |
| backend `ruff check` + `black --check` | ✅ clean (67 files) | 2026-10-08 |
| `backend/frontend-react` vitest | ✅ 105/105 (incl. single-client gate) | 2026-10-08 |
| `backend/frontend-react` build | ✅ vite + PWA sw generated | 2026-10-08 |
| `alembic upgrade head --sql` (offline) | ✅ 47 DDL stmts to 008 | 2026-10-08 |
| `alembic upgrade head` vs live DB | ⬜ not run — docker daemon down | — |
| Full suite w/ `make test` | ⬜ not run this session (pytest used directly) | — |

> Rule: mark ⬜/⏳ honestly. Never upgrade a claim to ✅ without tool output.

## 6. Environment & config pointers

- Required env **names** (values in `.env`, never here): `DATABASE_URL`, `REDIS_URL`,
  `SECRET_KEY`, `ENVIRONMENT`, `OLLAMA_BASE_URL`, `STRIPE_SECRET_KEY`, `CORS_ORIGINS`,
  `POSTGRES_MCP_URL` (MCP only).
- Services must be up first: `docker compose up -d postgres redis` (compose v2 plugin; daemon must be running).
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
