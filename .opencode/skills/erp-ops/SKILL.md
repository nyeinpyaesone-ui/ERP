---
name: ERP Ops
description: CI/CD, secrets and environments contract, blue-green deploys, repo-guard, and host constraints for /home/admin/ERP - exact job graph, can_push/can_deploy logic, Trivy specifics, release flow, and flaky-network workarounds
---

# ERP Ops (CI/CD, deploys, repo hygiene)

## CI job graph (`.github/workflows/ci.yml`, all actions 40-char SHA-pinned, D-009)

config (detect) → { Secret Scan (Gitleaks), Code Quality (ruff+black enforced, mypy advisory), Tests (pytest 285 + alembic 001→008 on postgres:15), Frontend Build (lint+vitest+build) } → docker-backend + docker-frontend (push on main w/ can_push) → security (Trivy, SARIF×2) → Deploy to Staging / Deploy to Production.

- `config` computes: `can_push` = DOCKER_USER var + both `DOCKER_PAT_BACKEND`/`DOCKER_PAT_FRONTEND` secrets (both SET 2026-10-11). `can_deploy` additionally requires ALL of: `SSH_PRIVATE_KEY`, `STAGING_KNOWN_HOSTS`, `STAGING_HOST`, `STAGING_USER`, `PRODUCTION_KNOWN_HOSTS`, `PRODUCTION_HOST`, `PRODUCTION_USER` — absent → jobs SKIP (fail-closed, D-012; not a bug).
- Environments: `staging` (main pushes only) + `production` (v* tags only), protection on both (D-017). Deploy over SSH via `scripts/deploy-blue-green.sh` (sources `scripts/lib.sh`).
- Trivy: consumes the build jobs' single-line image ref (a "Resolve single image refs" step takes the FIRST line — metadata-action emits one ref per line; passing the raw multi-line value is the bug that used to kill the job). `exit-code` has no default → findings are advisory in SARIF, never fail CI (gating = pending policy call).
- Other workflows: codeql.yml (schedule+push), opencode.yml (event-guarded), release.yml (tag `v*` or dispatch → verify images → GitHub Release from CHANGELOG.md).
- Snyk is REMOVED (D-016) — Trivy is the only container scanner; do not reintroduce Snyk or unpinned actions.

## Repo guard / hygiene

- `make guard` → `scripts/repo-guard.sh`: fails on nested `.git` (T-019 incident class), missing tracked files, empty `scripts/*.sh`. Run after long background jobs, before pushes.
- Counts: never hardcode file/commit counts in README/STATUS (T-018 lesson) — use `git ls-files | wc -l`.
- Commits: Conventional Commits; `git push` needs retry loops here (intermittent GnuTLS to github.com); `gh api` usually works when git-over-https fails.
- `gh run watch <id> --interval 20 --exit-status` (no --compact flag). Get job ids: `gh run view <id> --json jobs --jq '.jobs[] | select(.name=="...") | .databaseId'`, logs via `gh run view <id> --job=<jobId> --log`.

## Host constraints (this machine)

- proot/Termux-class aarch64: Docker can NEVER run here (D-013/D-018; `/proc/self` uid 0 → newuidmap fails). Local DB path = native PG18/Redis binaries only. CI (postgres:15 service, both image builds) is the verification for anything container-related.
- `install.sh --preflight` detects runtime class and reports native-mode readiness.
- OpenCode harness: service restarts under memory pressure (upstream issue anomalyco/opencode#54567); opencode-ai/opencode is ARCHIVED — issues go to anomalyco/opencode.

## First-deploy checklist (blocked items = user inputs)

1. Set the 7 deploy secrets (G-01) → `can_deploy=true` → staging deploy activates on next main push.
2. `gh variable set STAGING_DOMAIN/PRODUCTION_DOMAIN` (G-02).
3. Staging server via `./install.sh` (G-03), then `./scripts/deploy-blue-green.sh staging v1.2.3` + `--rollback` drill (G-04), backup drill (G-09).
