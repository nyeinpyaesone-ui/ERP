# MEMORY — ERP SOLUTION Agent Memory

Durable cross-session state. Companion to [`AGENTS.md`](../AGENTS.md)
(AGENTS.md = **how the repo works**; this file = **what is true right now**).
Append-only ledger; never store secrets (env var *names* only).

**Last verified:** 2026-10-11 (session: hygiene + proot detect + env/CI correctness)

---

## 1. Verified snapshot

| Fact | Value | Source |
|------|-------|--------|
| Git HEAD | `42bd0e94` integration-audit sweep; **in sync with `origin/main`** | `git status -sb` |
| Worktree | **Clean** (0 dirty) | `git status --porcelain` |
| Tracked files | **272** (was 275; removed orphan package-lock.json + docker-build-push.sh, snyk workflow) | `git ls-files \| wc -l` |
| Node | v22.22.1 at `/usr/bin/node` | `node --version` |
| npm / npx | **10.9.2 on PATH** at `/home/admin/.local/bin` | `which npm npx` |
| npm fallback | `/tmp/opencode/npm10/…` volatile — re-bootstrap if gone; **Makefile still hardcodes this path** | `ls`, `Makefile:18` |
| Python | 3.14.4 (venv) — runs 285 tests; Docker image is 3.11-slim | `python --version` |
| Alembic chain | **001 → 008** (offline SQL emits; GIN index fixed in `bb7295f2` so live PG works) | `alembic upgrade head --sql` |
| Frontend (canonical) | `backend/frontend-react` — **105 vitest tests**, eslint 0 errors/127 warnings, vite build green | `npm test`/`lint`/`build` |
| CI workflows | `ci.yml`, `codeql.yml`, `opencode.yml`, `release.yml` (**snyk-container.yml removed** `ad13f2bb`) | `ls .github/workflows` |
| GitHub auth | **gh authenticated** as `nyeinpyaesone-ui` (was unauthenticated) | `gh auth status` |
| GitHub secrets | **0 configured** (SNYK_TOKEN gone with Snyk; DOCKER_PAT_*/SSH_* still missing) | `gh secret list` |
| GitHub variables | `DOCKER_USER=powerrangeranikg` set; **STAGING_DOMAIN / PRODUCTION_DOMAIN unset** | `gh api .../actions/variables` |
| GitHub environments | `staging` (main only) + `production` (v* tags only) **created 2026-10-11**, fail-closed; `Docker` orphan deleted; `copilot` auto-managed, left alone | `gh api .../environments` |
| Docker daemon | **Down** — host is **proot/Termux class on aarch64** (no uid_map, `/data/data/com.termux` exists) | `docker ps`, new `erp_detect_runtime_class` |
| Open PRs | 29 Dependabot; **PR #85 closed + branch deleted** (inverted junk PR, 21k node_modules tracked) | `gh pr list`, `gh pr view 85` |

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
| D-016 | **Trivy in `ci.yml` is the only container scanner**; `snyk-container.yml` + `SNYK_TOKEN` removed (`ad13f2bb`) | Snyk ran red on every build (token never configured) and duplicated Trivy; Dependabot's snyk bump stream dies with the file |
| D-017 | **GitHub environments `staging`/`production` are part of the deploy contract** — staging = branch `main` only, production = tag `v*` only, fail-closed | ci.yml declares `environment:` on both deploy jobs; without the environments the jobs die at the deployment-record step. `Docker`/tool-named envs are banned (orphans) |
| D-018 | **Hosts are classified before provisioning** (`erp_detect_runtime_class`: docker-capable / proot-termux / containerized / unknown) | This very host is proot/Termux aarch64 — Docker can never run here (D-013); installer must guide to native mode instead of `get.docker.com` + `systemctl` failing mid-flight |

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
- **Done (2026-10-11 hygiene + proot + env/CI):** deep audit then 8 commits
  (all local, **unpushed** per ask-gate): `.gitignore` TLS/secrets rules
  (`f6ffc7b1`); codeql.yml duplicate `timeout-minutes` removed — the file was
  rejected at queue time, killing every CodeQL run at 0s (`4dfeb278`);
  orphan root `package-lock.json` + superseded `docker-build-push.sh` deleted
  (`1f80d6b6`); **Snyk workflow removed** (Trivy remains; 4 docs swept —
  `ad13f2bb`); **`erp_detect_runtime_class`** + proot early-exit +
  `install.sh --preflight` native-mode report (`794101a9`, smoke-tested here:
  class=proot-termux, all native components ok, exit 0); Termux/arm64 docs +
  GitHub-Environments contract (`3daa791b`). GitHub side: `staging`
  (branch main) + `production` (tag v*) environments created fail-closed,
  orphan `Docker` env deleted, PR #85 (inverted, 21k junk files) closed and
  branch deleted. Root-caused all remote CI failures: Tests=alembic GIN bug
  (fixed locally in `bb7295f2`, unpushed), codeql=dup key (fixed), snyk=no
  token (workflow removed). Local env audited: `.env` 22 keys +
  `backend/.env` 23 keys, all compose `:?` vars set, ENVIRONMENT=dev both,
  gitignored — nothing to change.
- **Done (2026-10-11 push + first green CI):** pushed 9 commits on user
  approval (`3cce8346..bedd042e`), then fixed the one test failure the push
  exposed — fresh checkouts lack `backend/static/` (empty dirs are invisible
  to git) so `StaticFiles(directory="static")` raised on import and both
  health tests errored (283 passed, 2 errors). `os.makedirs(exist_ok=True)`
  before the mount (`59156a96`), pushed. **CI run 38116547621 = success**,
  CodeQL 38116547575 = success. First verified full pass: gitleaks, quality,
  tests (285 + **alembic 001→008 on a live postgres:15** — GIN fix
  proven), frontend build, **both Docker images built in CI**. Trivy +
  deploy jobs correctly skipped (  fail-closed: `can_push=false`, no
  `DOCKER_PAT_*` secrets — T-004).
- **Done (2026-10-11 integration audit + drift sweep):** audited every
  third-party integration's wiring (config → code → compose → docs):
  Stripe (payments.py, fail-closed 400) — modernized `stripe.error.*` to
  top-level `stripe.StripeError`/`stripe.SignatureVerificationError` (v8
  deprecation); Ollama (llm_service, 10/120s httpx timeouts) — wired;
  SMTP_* — **declared but unwired** (no mail service exists); SENTRY_DSN /
  OPENAI_API_KEY / AWS_* — **not read** (no SDKs); uploads = local
  UPLOAD_DIR; frontend reads only `VITE_API_URL` (default `/api/v1`), now
  documented in new `backend/frontend-react/.env.example`. T-015 drift
  sweep: README/STATUS counts (272 files/103 commits), infra row fixed
  (no ES/S3 in repo; Ollama/Docker/GHA are real), 56 v1 `docker-compose`
  CLI refs → v2, AGENTS.md 16→20 routers, profile chain/lint/coverage
  claims corrected, GITHUB_SECRETS §3 rebuilt from actual Settings.
  Verified: pytest 285, ruff+black clean, 0 v1 compose refs left.
- **Done (2026-10-11 continue):** pushed the 3 audit commits
  (`863009d7`…`42bd0e94`) on user continue; CI 38119431811 = success,
  CodeQL = success — second consecutive green full pipeline.

## 4. Open threads

| ID | Thread | Next action |
|----|--------|-------------|
| T-003 | ~~never applied to live PG~~ **resolved in CI 2026-10-11** — run 38116547621 applied `alembic upgrade head` 001→008 on a real postgres:15 service. Still not applied to a *persistent* local DB | Optional: native PG18 cluster for local persistent DB; CI covers every push |
| T-011 | **CI deploy jobs need `STAGING_KNOWN_HOSTS` + `PRODUCTION_KNOWN_HOSTS` secrets** (D-012) or they fail closed | Populate with `ssh-keyscan -H <host>` once, then pin. See docs/GITHUB_SECRETS.md §1 |
| T-012 | **Container builds now verified in CI** — run 38116547621 built both backend and frontend images green. Still never built *on this host* (proot class, D-013/D-018) | none for CI; local builds impossible by design |
| T-013 | ~~gh unauthenticated~~ **resolved 2026-10-11** — `gh auth status` clean as `nyeinpyaesone-ui`. Codespaces TLS timeout never retested | none (closed except optional Codespaces retest) |
| T-004 | GitHub **secrets still 0**: `DOCKER_PAT_BACKEND/FRONTEND`, `SSH_PRIVATE_KEY`, `STAGING_*`/`PRODUCTION_*` hosts+known_hosts all missing. `DOCKER_USER` var **is** set (`powerrangeranikg`) | `gh secret set` per docs/GITHUB_SECRETS.md; until then image push + deploys stay skipped |
| T-005 | Production server not provisioned (`.env.production`, services) | docs/END_USER_INSTALL.md |
| T-007 | ~~Commits not pushed~~ **resolved 2026-10-11** — 10 commits pushed (`bb7295f2`…`59156a96`), CI green | none (closed) |
| T-008 | GitHub reports **96 vulnerabilities (10 critical, 50 high)** on default branch (was 106/9) | Dependabot groups batch them; 29 open PRs — triage majors (T-009) |
| T-009 | Frontend moderate prod vulns remain — need breaking majors (react 19 / router 7 / tailwind 4, vite 7/8 in PRs) | batch upgrade epic after B1 |
| T-010 | `backend/.env` created (random SECRET_KEY, gitignored) — local dev only; Docker/CI use their own env | none (informational) |
| T-014 | **"Compact the whole repo, make it easy to reuse for client UI/UX"** — requested late in a prior session, no scope agreed | Needs an agreed target: which of the 12 modules to keep, and whether "reusable" means a theming layer, a template scaffold, or stripping the dead Legacy v1.8/v2.1 trees |
| T-015 | ~~Doc-drift batch~~ **resolved 2026-10-11** — README counts + infra row (ES/S3 → Ollama/Docker/GHA), STATUS_CHECKLIST 259/64→272/103, 56 `docker-compose ` v1 CLI refs → v2 across 10 docs, AGENTS.md 16→20 routers, profile 001–006→001–008 / strict-TS→eslint / 80%→58% claims, GITHUB_SECRETS §3 rewritten to actual `Settings` wiring (SMTP reserved-unwired, SENTRY/OPENAI/AWS not read) | Re-open if new drift appears; keep AGENTS.md + profiles in the same sweep |
| T-016 | `STAGING_DOMAIN` / `PRODUCTION_DOMAIN` repository variables **unset** — deploy jobs' GitHub-Deployment target_url renders empty | `gh variable set STAGING_DOMAIN --body …` once real hostnames exist |

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
| 4 workflows: strict YAML (dup-key loader) + pin audit | ✅ 0 dup keys, 0 unpinned, all parse (snyk file gone) | 2026-10-11 |
| `install.sh --preflight` smoke on this host | ✅ runtime-class proot-termux, native components ok, exit 0 | 2026-10-11 |
| new `.gitignore` rules vs tracked files | ✅ `git check-ignore` no matches; status clean | 2026-10-11 |
| session diff vs origin/main: secret scan | ✅ 0 secret-like strings (8 commits) | 2026-10-11 |
| GitHub environments `staging`/`production` | ✅ created; policies branch `main` / tag `v*`; orphan `Docker` deleted | 2026-10-11 |
| `gh auth status` | ✅ authenticated `nyeinpyaesone-ui` | 2026-10-11 |
| **CI run 38116547621 (main, `59156a96`)** | ✅ **success** — gitleaks, quality, tests, frontend build, both Docker images built | 2026-10-11 |
| **CI run 38119431811 + CodeQL (main, `42bd0e94`)** | ✅ both success — integration audit + drift sweep push re-verified everything | 2026-10-11 |
| CodeQL run 38116547575 | ✅ success (dup-key fix proven; python/js/actions analyzes green) | 2026-10-11 |
| `alembic upgrade head` vs live DB | ✅ in CI — 001→008 applied to postgres:15 (8 "Running upgrade" lines) | 2026-10-11 |
| CI pytest / vitest | ✅ 285 passed / 105 passed (with `backend/static/` absent → makedirs fix `59156a96`) | 2026-10-11 |
| Trivy + deploy jobs | ⏳ skipped in CI — `can_push=false` until `DOCKER_PAT_*`/SSH secrets exist (T-004) | 2026-10-11 |
| `docker build` backend + frontend on **this host** | ⬜ impossible — proot class (D-013/D-018); CI builds are the verification | — |
| pytest local re-run after static-dir fix | ✅ 285 passed with `static/` removed (CI-faithful), ruff+black clean on `main.py` | 2026-10-11 |
| frontend lint/build (unchanged since 10-08) | ⏳ CI frontend-build job green today = de-facto re-verify; local not re-run | 2026-10-11 (CI) |

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
