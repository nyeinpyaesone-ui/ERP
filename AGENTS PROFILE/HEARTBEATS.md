# HEARTBEATS — Cadence, Checklists & Verification Gates

Scope: **when to stop and check**. What each check inspects: facts in
[`AGENTS.md`](../AGENTS.md), state in [MEMORY.md](MEMORY.md), routing in
[SKILLS.md](SKILLS.md).

## 0. Heartbeat triggers

Run the matching beat whenever any of these fires:
new session · task milestone (plan → after edits → before report) · before any
commit/push · after DB/docker/CI-affecting change · user says "check/verify" ·
context compaction or long silence.

---

## Beat A — Session start (orientation)

- [ ] Read `AGENTS.md` → `MEMORY.md` §1/§4/§5 (auto-loaded via `instructions`).
- [ ] Re-verify snapshot: `git status --short`, `git log --oneline -5`,
      `node --version`, `npm --version` — reconcile against MEMORY §1; log drift §4.
- [ ] Services: `docker-compose ps` (or `docker ps`) — remember backend/MCP need
      `postgres redis` up.
- [ ] Open threads: pick work from MEMORY §4 / [IMPROVEMENTS.md](IMPROVEMENTS.md);
      if a dirty worktree exists (T-001), resolve its plan **before** new edits.
- [ ] `todowrite` a 3–8 item plan for non-trivial work; exactly one `in_progress`.

## Beat B — After any code/config edit

- [ ] Changed Python → run targeted `pytest` in `backend/venv`
      (`pytest.ini` supplies `pythonpath` — never move it to `pyproject.toml`).
- [ ] Changed frontend → `cd backend/frontend-react && npm run build`
      (and `npm run test` for logic; vitest exists).
- [ ] Changed permissions/RBAC → `pytest backend/app/tests/test_permission_consistency.py`
      (and `test_route_permissions.py`); every `require_permission()` must map to
      `permissions_catalogue.py`.
- [ ] Changed migrations → confirm chain still linear (`alembic upgrade head`
      when DB up; chain is 001–006).
- [ ] Touched `opencode.json`/skills → `customize-opencode` skill was loaded first.
- [ ] Diff review: `git diff --stat` — no secrets, no `venv/`, `node_modules/`,
      `dist/`, `*.heapsnapshot`, session files, `.env*`.

## Beat C — Before reporting done

- [ ] Every claimed result backed by tool output; update MEMORY §5
      (✅/⬜/⏳ honestly — never upgrade ⬜ to ✅ without evidence).
- [ ] `make test` for cross-stack verification — expected known gaps:
      frontend lint is a **no-op** (no lint config), watch for PATH issues.
- [ ] New durable facts → MEMORY §1; decisions → §2; leftovers → §4.
- [ ] Deliverable exists at the promised path; answer ≤4 lines unless detail asked.

## Beat D — Session end (memory write)

- [ ] Append (don't rewrite) MEMORY §3 progress with what actually landed.
- [ ] Refresh §1 rows that changed (HEAD, dirty state, versions).
- [ ] Move closed threads out of §4; add any new AGENTS.md drift.
- [ ] No commits unless the user explicitly asked; if asked: Conventional Commit,
      stage only intended files, `git push` hits the ask-gate.

## Red flags → stop and reconcile

| Signal | Action |
|--------|--------|
| Test/lint result contradicts expectation | Log to MEMORY §4 before any "done" claim |
| AGENTS.md conflicts with observed behavior | Live evidence wins → drift entry (T-002 pattern) |
| Dirty files you didn't touch | Do not clobber; map origin (T-001) first |
| MCP postgres fails | Check `POSTGRES_MCP_URL` + container up (TOOLS §2) |
| `npx/npm` missing | PATH regression → npm10 fallback (TOOLS §5) |
| About to `git push` / `rm -rf` | These are ask-gates — prompt, don't proceed |

## Heartbeat cadence summary

| Beat | Trigger | Output |
|------|---------|--------|
| A Start | new session | verified snapshot + plan |
| B Edit | after each change | passing targeted checks |
| C Done | before report | evidence-backed claims, updated §5 |
| D End | session close | appended memory |
