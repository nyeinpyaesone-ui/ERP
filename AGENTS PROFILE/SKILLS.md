# SKILLS — Task → Skill → Verification Matrix

Scope: **the right capability for each task type**, matched so every part of the
profile set has exactly one owner: facts → [`AGENTS.md`](../AGENTS.md) ·
state → [MEMORY.md](MEMORY.md) · tools → [TOOLS.md](TOOLS.md) ·
delegation → [SUB-AGENTS.md](SUB-AGENTS.md) · timing → [HEARTBEATS.md](HEARTBEATS.md) ·
values → [SOUL.md](SOUL.md) · backlog → [IMPROVEMENTS.md](IMPROVEMENTS.md).

## How skills are used

1. Match the task row below → note the **approach** and **verify** commands.
2. If the row says *load skill*, call the `skill` tool first (it injects its rules
   into the session), then act.
3. Installed skills: **`customize-opencode`** (config edits only). Repo has no
   `SKILL.md` yet — to add one: create file → add row here → mention in TOOLS §3.

## Matrix

| # | Task type | Skill / approach | Primary tools | Verify (gate) |
|---|-----------|------------------|---------------|---------------|
| 1 | Edit opencode config, agents, skills, MCP | **Load `customize-opencode` skill** (mandatory) | skill → edit | Config still valid JSON/JSONC; MCP still starts |
| 2 | Understand code / find "where is X" | explore-first; read `main.py`, `models.py`, routers | `task(explore)` ∥ glob/grep | Claims cite `file:line` |
| 3 | Backend feature/bug (FastAPI/SQLAlchemy) | Follow existing router/service patterns; PEP 8 + type hints; no comments unless asked | read/edit → bash | `backend/venv … pytest` (targeted) + Beat B |
| 4 | RBAC / permissions change | Edit `permissions_catalogue.py` **first**, then router; keep `has_permission` only in `services/permissions.py` | edit → bash | `test_permission_consistency.py`, `test_route_permissions.py` |
| 5 | DB migration | `alembic revision --autogenerate -m "desc"`; keep chain linear (001–006) | bash | `alembic upgrade head` on running PG; chain `ls versions/` |
| 6 | Frontend change (React/Vite) | Only in `backend/frontend-react`; React 18 + strict TS conventions; no lint config exists — don't invent compliance | edit → bash | `npm run build` + `npm run test` |
| 7 | Frontend dependency/install | npm 10.9.2 on PATH; fallback `node /tmp/opencode/npm10/package/bin/npm-cli.js` | bash | `npm --version`; lockfile diff sane |
| 8 | Tests (add/fix) | Place under `backend/app/tests/`; pytest config comes from `pytest.ini` | edit → bash | `pytest -q`; coverage intent 80% (CONTRIBUTING) |
| 9 | Docker image change | Multi-stage preferred (current backend Dockerfile is single-stage → IMP-P1-1) | edit → bash | `docker build` / `docker-compose config` |
| 10 | Deploy / release | Blue-green `scripts/deploy-blue-green.sh`; legacy `deploy.sh` deprecated (IMP-P1-2) | bash | `health-check.sh`; rollback rehearsed |
| 11 | Postgres data queries | MCP `postgres` (export `POSTGRES_MCP_URL` + container up) | mcp postgres | Query returns rows, no traceback |
| 12 | Browser/E2E (portal flows) | Playwright MCP or `playwright_browser_*`; target dev server URL from `npm run dev` | playwright | Screenshot/snapshot evidence |
| 13 | Docs update | Match existing doc tables/voice; update TOC/links; AGENTS.md owns repo facts | read/write | Links resolve; no stale claims (drift → MEMORY §4) |
| 14 | Git commit / PR | Conventional Commits (`feat:`…); stage intended files only | bash | `git status` clean of secrets; CI green (never push unless asked) |
| 15 | CI workflow change | `ci.yml` jobs: secret-scan → quality → test → frontend-build → docker → security → deploys; builds `backend/frontend-react/dist/` | read/edit | `docker-compose config`-level sanity; Actions run on push |
| 16 | Ambiguous/multi-step problem | `sequential-thinking` tool → `todowrite` plan → execute | sequential-thinking, todowrite | Plan matches delivered scope |
| 17 | Need user decision | `question` tool with concrete options (recommendation first) | question | Choice recorded in MEMORY if durable |
| 18 | Large-output digest (tool dumps, CI logs) | Delegate to explore agent with size cap | task(explore) | Digest ≤ stated word cap |
| 19 | Security-sensitive (secrets, prod, `.env`) | Read names only; GitHub secrets via `docs/GITHUB_SECRETS.md`; never print values | read, webfetch | `git diff` has no secret material |
| 20 | This profile set (`AGENTS PROFILE/*`) | Main agent only (never delegated); append-only MEMORY; cross-links intact | write/edit | README index ↔ files match; IDs referenced by MEMORY exist |

## Matching rules (so parts don't collide)

- **One fact, one file.** If a statement belongs to two files, it belongs to
  AGENTS.md (facts) or MEMORY (state) — the other file links instead.
- **ID referential integrity:** MEMORY `T-00x` ↔ IMPROVEMENTS `IMP-Px-x` must
  resolve; deleting an item requires updating the referencer (Beats C/D).
- **Escalation path:** task above fails its *Verify* gate twice → log to
  MEMORY §4 and surface in [IMPROVEMENTS.md](IMPROVEMENTS.md) rather than
  silently retrying.
- **Skill gap:** row needed but missing → create `SKILL.md`/profile file first,
  then do the task (setup-before-execution).

## Repo system-improvement emphasis

Improvement work is sequenced in [IMPROVEMENTS.md](IMPROVEMENTS.md); always pull
the **highest-priority item whose files you already have open**, and run its
*Verify* before marking done (Beat C). P0 items (dirty worktree, live migrations,
AGENTS.md drift, CI truthfulness) gate everything else.
