# ERP SOLUTION — Remaining Work Plan

**Superseded:** the 2026-09-26 execution plan (Phases 0–10) — obsolete; ~90% of it is
already done and several directives would regress fixed bugs (see §1).
**Status date:** 2026-10-11 · **Live state source of truth:** `AGENTS PROFILE/MEMORY.md` §4

---

## 0. How to read this plan

This tracks only what is **genuinely open**. Everything already verified lives in
`MEMORY.md` (§1 snapshot, §5 ledger) — do not re-plan it. Items are ID'd by open
thread (T-0xx) or gap (G-xx) so MEMORY and this file stay in sync.

## 1. Guardrails — do NOT regress these (each maps to a decision)

| Don't | Because |
|---|---|
| Pin actions to anything but a 40-char SHA + `# vX.Y.Z` | D-009 — `trivy-action@master` was the original supply-chain bug |
| Add `--cov-fail-under` to CI, or move the floor out of `backend/pyproject.toml` | D-010 — single source of truth (floor = 58) |
| Write `ENVIRONMENT=production` anywhere | D-014 — `Literal["dev","test","prod"]`; `production` raises at import |
| Reintroduce Snyk / `SNYK_TOKEN` | D-016 — Trivy is the only container scanner |
| Replace `backend/pytest.ini` or add asyncpg fixtures | D-003/D-011 — sync SQLAlchemy + SQLite-in-memory tests are the working design |
| Build `/frontend` instead of `frontend-react` | D-001 |
| Delete `staging`/`production` GitHub environments or skip branch/tag protection | D-017 — deploy jobs die without them |
| Run containers on this host as a plan step | D-013/D-018 — proot/Termux aarch64; native PG18/Redis or CI is the path |

## 2. Open items

| ID | Item | Blocked on | Validation when done | Owner |
|----|------|-----------|----------------------|-------|
| G-01 | **Deploy secrets**: `SSH_PRIVATE_KEY`, `STAGING_KNOWN_HOSTS`, `PRODUCTION_KNOWN_HOSTS` (T-004). `DOCKER_PAT_BACKEND/FRONTEND` set 2026-10-11 | User values (never commit them) | Next main-push CI: image push + Trivy jobs run (no longer `can_push=false`); deploy jobs leave "skipped" | User |
| G-02 | **Repository variables** `STAGING_DOMAIN` / `PRODUCTION_DOMAIN` (T-016) | Real hostnames | `gh variable list` shows both; deploy job target_url non-empty | User |
| G-03 | **Staging server provisioning** (T-005) | A server (4GB/2vCPU/50GB, Ubuntu 22.04) | `./install.sh --preflight` reports `docker-capable`; compose up; `/health` 200 via nginx | Ops |
| G-04 | **First staging deploy** — blue-green dry-run + rollback drill | G-01 + G-03 | `./scripts/deploy-blue-green.sh staging v1.2.3` then `--rollback`; both exit 0, upstream switches | Ops |
| G-05 | **Vulnerability triage** (T-008: 96 alerts, 10 critical / 50 high; T-009: frontend breaking majors — React 19, router 7, Tailwind 4, Vite 7/8) | Dedicated upgrade epic | Alert count drops via `gh api`; full suite green after each batched major (pytest 285, vitest 105, build) | Dev |
| G-06 | **Monitoring decision + minimal slice** — Prometheus/Grafana (or managed) + structured access logs; only `/health` + `/ready` exist today | Self-hosted vs managed choice; G-05 effort split | Dashboard shows p95/error rate/DB pool from a load smoke; one alert rule fires in a drill | Ops/Dev |
| G-07 | **Rate limiting** — nginx + Redis sliding window on `/api/v1/auth` | G-03 | Burst test returns 429s; legit traffic unaffected | Dev |
| G-08 | **Ops docs**: `RUNBOOK.md` (deploy/rollback/incident), `DISASTER_RECOVERY.md` (RTO<15m/RPO<1m drill), `DEVELOPER_ONBOARDING.md` | G-04 (document a rehearsed deploy) | A fresh clone + the docs alone reproduces a staging deploy | Dev |
| G-09 | **Backup drill** — `scripts/backup.sh` pg_dump, then `pg_restore` into a scratch DB | G-03 | Restored DB passes `alembic current` + smoke queries | Ops |
| G-10 | **Task-bot containment** (T-019) — identify the automation behind "qwen-chat coder" (junk PR #135 + empty `git init` in `scripts/` that wiped 14 files on 2026-10-11 ~23:26) | User access to that automation | No further unexplained worktree changes; nested `.git` never reappears | User |
| G-11 | **Repo reuse/theming** (T-014) — "compact the repo, make reusable for client UI/UX" | User scoping: which of the 12 modules stay; theming layer vs template scaffold vs stripping dead v1.8/v2.1 trees | — | User then Dev |

## 3. Suggested order

1. **G-10** (stop the bleeding), then **G-01 + G-02** (user, unblocks everything remote), then **G-03**
2. **G-04 + G-09** on staging, then **G-08** documents what was rehearsed
3. **G-05** as a focused epic (biggest bang: 96 alerts); **G-07** rides along
4. **G-06** once there is traffic worth monitoring
5. **G-11** last — needs a product conversation, not a sprint

## 4. Explicitly closed (reference only — do not reopen)

Phase 0–4 of the old plan (compose, rebase, alembic 001–008, async fixes,
285+105 tests, CI green with SHA-pinned workflows + image builds), Phase 5
compose/blue-green scripts, Phase 8 Trivy, Phase 9 backup script, Phase 10
DEPLOYMENT_GUIDE — all verified in `MEMORY.md` §5. Coverage floor is 58
(58.89% measured); the old plan's 80% target is not adopted (D-010).
