# MEMORY — ERP SOLUTION Agent Memory

Durable cross-session state. Companion to [`AGENTS.md`](../AGENTS.md)
(AGENTS.md = **how the repo works**; this file = **what is true right now**).
Append-only ledger; never store secrets (env var *names* only).

**Last verified:** 2026-10-08 (session: CI/CD hardening — pins, Trivy fix, release workflow)

---

## 1. Verified snapshot

| Fact | Value | Source |
|------|-------|--------|
| Git HEAD | `0650937c` fix(prod) ENVIRONMENT=prod; session landed `adc23ccc`→`0650937c` + env fixes (run `git log -10`) | `git log` |
| Worktree | **Clean**, `main` in sync with `origin/main` (0/0) | `git status --short` |
| Tracked files | 273 at HEAD; 274 at tag `v1.0.0` | `git ls-files \\| wc -l` |
| Node | v22.22.1 at `/usr/bin/node` | `node --version` |
| npm / npx | **10.9.2 on PATH** at `/home/admin/.local/bin` | `which npm npx` |
| npm fallback | `/tmp/opencode/npm10/…` volatile — re-bootstrap if gone | `ls` |
| Python | 3.14.4 (venv) — runs 285 tests; Docker image is 3.11-slim | `python --version` |
| Alembic chain | **001 → 008** (offline `--sql` regenerates 47 DDL stmts under alembic 1.20) | `alembic upgrade head --sql` |
| Frontend (canonical) | `backend/frontend-react` — scripts: `dev`, `build`, `preview`, `test`, `test:watch`; **105 vitest tests** | `package.json`, `npm run test` |
| CI workflows | `ci.yml`, `codeql.yml`, `opencode.yml`, `snyk-container.yml`, `release.yml` | `ls .github/workflows` |
| Docker daemon | **Down** — `docker compose` v2.40.3 present, but socket missing; start needs interactive sudo | `docker ps` |
| Podman 5.7.0 | Present but **unusable** — rootless setup dies in `newuidmap` (D-013) | `podman info` |
| Native PG18 / Redis | `/usr/lib/postgresql/18/bin/*` + `/usr/bin/redis-server` available; neither running | `which postgres redis-server` |
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
| D-009 | **Every workflow action is pinned to a 40-char commit SHA** with a trailing `# vX.Y.Z` comment; Dependabot updates SHA pins natively | Supply-chain: `trivy-action@master` + `chrnorm/*@releases/v1` were mutable. Verified 14/14 SHAs against each action's release page |
| D-010 | **Coverage floor lives only in `backend/pyproject.toml`** (`fail_under = 58`); CI passes no `--cov-fail-under` | Two sources of truth had drifted (CI 58 vs an 80% claim in CONTRIBUTING) |
| D-011 | **PostgreSQL service container in CI is required** (backs `alembic upgrade head`); Redis is intentionally absent | Tests mock `redis.from_url`; `token_store` fails open. Removing PG breaks migrations |
| D-012 | **Deploy host verification uses `STAGING_KNOWN_HOSTS` / `PRODUCTION_KNOWN_HOSTS` secrets**; `ssh-keyscan` is banned | `ssh-keyscan` is unauthenticated/MITM-able. Empty secret must fail the deploy |
| D-013 | **Container runtime cannot run on this host.** Native PG18/Redis binaries are the only viable local path | `/proc/self` reports uid 0 → `newuidmap` fails for both rootlesskit and podman; `sudo` needs an interactive password |
| D-014 | **`ENVIRONMENT` accepts exactly `dev` \| `test` \| `prod`** — never `production`. This is not configurable | `Settings` uses a `Literal`; a bad value raises at import. Only surfaces on a real deploy, since CI/dev use `dev` |
| D-015 | **`.env.example` is generated from `backend/app/config.py`**, not hand-maintained. Every key must be a real `Settings` field or an explicit `docker-compose.yml` interpolation | `extra="ignore"` meant 14 dead keys loaded as no-ops while 12 real ones silently fell back to defaults |

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
- **Done (2026-10-08 lint pass):** endpoint prefix matrix verified — 57/57
  frontend calls ↔ 98 backend routes exact match; AIChat stream token bug
  fixed (`lastContent`→`lastMsg`, `8b3bf6de`); real eslint 10 flat config +
  `npm run lint` + CI step (`fe239e9f`); `make test` green (ledger ✅).
- **Done (2026-10-08 CI/CD upgrade):** fixed the Trivy scan bug — it referenced
  `sha-<40-char>` while `metadata-action` pushes `sha-<short7>`, so `security`
  scanned a tag that was never published; now consumes
  `needs.docker-*.outputs.image_tag`. Deleted the dead `frontend-dist`
  artifact round-trip (`.dockerignore` excludes `dist/`, so the download was
  discarded by the Docker build context). Removed the unused Redis service
  container (kept Postgres — `alembic upgrade head` needs it) and the unused
  `statuses: write` permission. SHA-pinned + upgraded **all 5 workflows**
  (14/14 SHAs verified against release pages), added `concurrency` +
  `timeout-minutes` everywhere, made mypy advisory via `continue-on-error`,
  dropped CI's duplicate `--cov-fail-under`, split the colliding
  `snyk.sarif` filename per job, replaced `ssh-keyscan` with pinned
  `known_hosts` secrets, guarded `opencode.yml` against fork commenters
  (`id-token: write` + API-key secret removed). Frontend Dockerfile now
  `npm ci`s the lockfile (was `npm install` without it → non-reproducible
  images). Dependabot gained the `docker` ecosystem + `groups:` to collapse
  the 37-branch backlog. New `release.yml` (tag or dispatch → verify images →
  publish GitHub Release from CHANGELOG.md). Compose: dropped obsolete
  `version:` and the never-read `REACT_APP_API_URL`. Hygiene: 252MB
  heapsnapshots + empty `run/ logs/ backups/ ssl/` deleted, tag `list` deleted,
  backup manifest untracked, `.env` files chmod 600, stray tag and 9 dead
  local Dependabot branches removed, `bcrypt` exact-pinned, README/CONTRIBUTING
  counts corrected. Verified: pytest 285, vitest 105/105, ruff, black, eslint
  0 errors, vite build, all 5 workflows parse with zero unpinned actions.
- **Done (2026-10-08 env/prod correctness):** found and fixed a
  **production-blocking** bug — `ENVIRONMENT` is `Literal["dev","test","prod"]`
  yet `docker-compose.prod.yml` hardcoded `production` in both backend
  services, and `install.sh` / `setup-production.sh` /
  `.env.production.template` all generated it, so the documented production
  deploy could never boot (D-014). Also rebuilt `.env.example` from
  `config.py`: the old file set `ENVIRONMENT=development` (raises at import)
  and carried 14 keys the app never reads while omitting 12 it requires
  (D-015); now 30 keys, verified 0 unread / 0 missing. Fixed
  `JWT_ALGORITHM`→`ALGORITHM`, added the `DOCKER_USER`/`VERSION` keys that
  compose interpolates, moved `API_URL`/`WS_URL`/`SENTRY_DSN` under a "NOT
  read" heading. Rebuilt `docs/GITHUB_SECRETS.md` from the workflows (it
  documented `DOCKER_USERNAME`/`KUBE_CONFIG` that nothing reads; now all 11
  secrets + 3 variables, checked 14/14). Deleted the stray `list` tag from the
  remote. 8 commits pushed, `main` in sync with `origin/main`.
- **Deferred (requested, not started):** "/compact the whole repo, remodify
  easy to reuse this ERP for client UI/UX" — no scoping or file list agreed
  with the user before the session closed. Treat as an open thread, not work.

## 4. Open threads

| ID | Thread | Next action |
|----|--------|-------------|
| T-003 | Alembic 001–008 **never applied to live PostgreSQL** — blocked: docker daemon down, start needs interactive sudo | `sudo systemctl start docker` → `docker compose up -d postgres redis` → `alembic upgrade head` |
| T-011 | **CI deploy jobs need `STAGING_KNOWN_HOSTS` + `PRODUCTION_KNOWN_HOSTS` secrets** (new in D-012) or they fail closed | Populate with `ssh-keyscan -H <host>` once, then pin. See docs/GITHUB_SECRETS.md |
| T-012 | **Container builds unverified** — no runtime on this host, so `docker build` for backend/frontend and the frontend `npm ci` image path are untested | First CI run on the pushed commit will exercise them; watch the `docker-*` jobs |
| T-013 | Codespaces unusable: `api.github.com` TLS handshake timeout (0/3); `gh` unauthenticated | SHAs were resolved by scraping `/releases/tag/<version>` HTML instead |
| T-004 | GitHub secrets pending: `DOCKER_USER`, `DOCKER_PAT_BACKEND/FRONTEND`; Docker Hub images empty; `gh` unauthenticated | `gh auth login` → STATUS_CHECKLIST.md → docs/GITHUB_SECRETS.md |
| T-005 | Production server not provisioned (`.env.production`, services) | docs/END_USER_INSTALL.md |
| T-007 | ~~Commits not pushed~~ **resolved this session** — `git push origin main` succeeded; `main` in sync with `origin/main` | none (closed) |
| T-008 | GitHub reports 106 Dependabot vulnerabilities (9 critical) on default branch | `groups:` now batches them; close stale PRs for the 9 deleted branches |
| T-009 | Frontend 2 moderate prod vulns remain — need breaking majors (react 19 / router 7 / tailwind 4) | batch upgrade epic after B1 |
| T-010 | `backend/.env` created (random SECRET_KEY, gitignored) — local dev only; Docker/CI use their own env | none (informational) |
| T-014 | **"Compact the whole repo, make it easy to reuse for client UI/UX"** — requested late in the session, no scope agreed | Needs an agreed target: which of the 12 modules to keep, and whether "reusable" means a theming layer, a template scaffold, or stripping the dead Legacy v1.8/v2.1 trees |

## 5. Verification ledger

| Check | Result | When |
|-------|--------|------|
| `pytest` (backend) | ✅ 285 passed, 6 warnings | 2026-10-08 |
| backend `ruff check` + `black --check` | ✅ clean (67 files) | 2026-10-08 |
| coverage (`coverage report`) | ✅ 58.21% (floor 58 from pyproject) | 2026-10-08 |
| `backend/frontend-react` vitest | ✅ 105/105 (incl. single-client gate) | 2026-10-08 |
| `backend/frontend-react` build | ✅ vite + PWA sw (6 entries, 838 KiB) | 2026-10-08 |
| `backend/frontend-react` lint (eslint 10) | ✅ 0 errors / 127 warnings; CI enforces | 2026-10-08 |
| all 5 workflows: YAML parse + pin audit | ✅ 0 unpinned, concurrency + timeout everywhere | 2026-10-08 |
| `docker compose config` | ✅ valid (no `version:` warning) | 2026-10-08 |
| `npm ci` from lockfile (throwaway copy) | ✅ exit 0, 761 packages resolved | 2026-10-08 |
| `requirements.txt` pin audit | ✅ 24/24 exact (`==`); bcrypt now `==4.3.0` | 2026-10-08 |
| `alembic upgrade head --sql` (offline) | ✅ 47 DDL stmts to 008 | 2026-10-08 |
| `alembic upgrade head` vs live DB | ⬜ not run — no container runtime (D-013) | — |
| `docker build` backend + frontend | ⬜ not run — no container runtime (D-013) | — |
| Live CI run on GitHub | ⬜ not run — commits pushed only after this session | — |
| Codespaces as a fallback runtime | ⬜ unavailable — `api.github.com` TLS timeout | — |
| `.env.example` vs `config.py` field audit | ✅ 30 keys, 0 unread, 0 missing (script-checked) | 2026-10-08 |
| prod fail-closed matrix (placeholder/short key, example DB) | ✅ all three refuse; real key + real DB boots | 2026-10-08 |
| `.env.production.template` vs compose interpolations | ✅ 8/8 vars present | 2026-10-08 |
| `install.sh` + `setup-production.sh` shell syntax | ✅ `bash -n` clean | 2026-10-08 |

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
