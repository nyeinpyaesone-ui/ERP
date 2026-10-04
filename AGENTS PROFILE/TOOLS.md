# TOOLS — Inventory, Permission Gates & Command Cheatsheet

Scope: **what can be invoked and how**. Task → tool routing lives in
[SKILLS.md](SKILLS.md); delegation of tools in [SUB-AGENTS.md](SUB-AGENTS.md).
Source of permission truth: [`../opencode.json`](../opencode.json).

## 1. Built-in tools (opencode session)

| Group | Tools | Notes for this repo |
|-------|-------|---------------------|
| Read | `read`, `filesystem_read_*`, `filesystem_get_file_info` | Read images/PDFs natively; use offset/limit on large files |
| Search | `glob`, `grep`, `filesystem_search_files`, `filesystem_directory_tree` | Prefer over bash `find`/`grep`. **`.opencode/node_modules` and `backups/` are huge** — scope `path` always |
| Write/Edit | `write`, `edit`, `filesystem_edit_file` | Read before edit; no comments unless asked; never write secrets |
| Shell | `bash` (persistent session) | Quote paths with spaces (`AGENTS PROFILE/`). Batch independent calls. Large output → saved to file, then Grep/Read |
| Web | `webfetch`, `websearch` | Never invent URLs; HTTP→HTTPS automatic |
| Browser | `playwright_browser_*` | For E2E/PWA checks against the React portal |
| Coordination | `todowrite`, `task` (sub-agents), `question` | See [HEARTBEATS.md](HEARTBEATS.md) for todo discipline |
| Cognition | `sequential-thinking_sequentialthinking` | Multi-step/ambiguous problems only |
| Skill | `skill` | Loads injectable instructions — see §3 |

## 2. MCP servers (from `opencode.json`)

| Server | Command | Gate / gotcha |
|--------|---------|---------------|
| `postgres` | `bash scripts/mcp-postgres.sh` | Requires `export POSTGRES_MCP_URL=...` **and** Postgres running (`docker-compose up -d postgres`); wrapper exits 1 otherwise |
| `filesystem` | `npx -y @modelcontextprotocol/server-filesystem /home/admin/ERP/backend` | **Scoped to `backend/`** — root/other dirs need normal tools |
| `playwright` | `npx -y @playwright/mcp` | Browser automation |
| `sequential-thinking` | `npx -y @modelcontextprotocol/server-sequential-thinking` | Reasoning aid |

## 3. Skills

- Loadable via `skill` tool; **installed: `customize-opencode` only** — mandatory
  before editing `opencode.json`, `.opencode/`, `~/.config/opencode/*`, agents,
  or skills.
- No repo-specific skills exist yet (no `SKILL.md` in repo). Adding one = new file
  + row in this table + routing rule in [SKILLS.md](SKILLS.md).

## 4. Permission gates (`opencode.json → permission`)

| Action | Policy |
|--------|--------|
| read / glob / grep / list / edit / webfetch / websearch | allow |
| `bash *` | allow |
| `bash git push *` | **ask** |
| `bash rm -rf *` | **ask** |
| Watcher ignores | `__pycache__`, `*.pyc`, `backend/venv/**`, `node_modules/**`, `backend/frontend-react/dist/**`, `scripts/backups/**`, `.git/**` |

## 5. Command cheatsheet (repo commands: `../AGENTS.md → Key Commands`)

```bash
# Services first — backend/MCP fail without them
docker-compose up -d postgres redis

# Backend
cd backend && source venv/bin/activate && uvicorn app.main:app --reload
cd backend && source venv/bin/activate && pytest           # pytest.ini supplies pythonpath
cd backend && source venv/bin/activate && alembic upgrade head   # chain is 001–006

# Frontend (canonical: backend/frontend-react)
cd backend/frontend-react && npm run dev      # npm 10.9.2 now on PATH
cd backend/frontend-react && npm run build
cd backend/frontend-react && npm run test     # vitest

# Stack / deploy
docker-compose up -d backend frontend
docker-compose -f docker-compose.prod.yml up -d
./scripts/deploy-blue-green.sh production v1.2.3 [--rollback]
make test   # backend + frontend steps (see HEARTBEATS gates)
```

**Fallback:** if PATH loses npm, use
`node /tmp/opencode/npm10/package/bin/npm-cli.js <cmd>` (re-bootstrap:
`npm i -g npm@10.9.2 --prefix /tmp/opencode/npm10`).

## 6. Script inventory (`scripts/`)

`setup.sh`, `deploy-blue-green.sh`, `rollback.sh`, `backup.sh`, `health-check.sh`,
`gh-manager.sh`, `verify-push.sh`, `setup-deploy.sh`, `setup-production.sh`,
`setup-ssl.sh`, `notify.sh`, `project-stats.sh`, `mcp-postgres.sh`
(⚠️ ignore `*.heapsnapshot` ≈233 MB and `backups/` — gitignored).

## 7. Environment variables (names only — values never here)

Backend: `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ENVIRONMENT`,
`OLLAMA_BASE_URL`, `CORS_ORIGINS`, `STRIPE_SECRET_KEY`.
MCP: `POSTGRES_MCP_URL`.
Full key list: `../.env.example`. Treat `.env*` as read-only, gitignored.

## 8. Doc map (where knowledge lives)

- Root: `README`, `CONTRIBUTING` (commits/PR), `CHANGELOG` (v1.0.0),
  `STATUS_CHECKLIST` (pending secrets/pushes), `ROADMAP` (v1.1.0→v2.0.0),
  `SECURITY`, deployment guides (Docker/GitHub secrets).
- `docs/`: ONBOARDING, API_SUMMARY, TESTING, DATABASE_MIGRATIONS,
  ARCHITECTURE_DECISIONS, PRODUCTION_*, BLUE_GREEN_DEPLOYMENT, BACKUP_RESTORE,
  SSL_CERTIFICATES, TROUBLESHOOTING, FAQ, END_USER_INSTALL, GITHUB_SECRETS.
- Code truth: `backend/app/main.py` (wiring), `models.py` (schema),
  `permissions_catalogue.py` (RBAC).
