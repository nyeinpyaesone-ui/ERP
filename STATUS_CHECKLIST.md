# ERP SOLUTION — Deployment Configuration Status

Verified: 2026-11-08
Active deployment path: GitHub Actions → Docker Hub → Docker Compose blue-green
Kubernetes: separate scaffold; not connected to the current CI/CD pipeline.

## Completed

- [x] PR #154 merged to main: secret manifest removed, Kustomize secret references documented, staging rollback and release workflow hardening completed.
- [x] Main CI after merge passed: run 42465025608.
- [x] Gitleaks, CodeQL, Ruff, Black, ESLint, backend tests, frontend build and Compose/shell validation passed in the merged PR CI.
- [x] Separate staging and production deployment gates exist.
- [x] Deployment requires explicit manual workflow-dispatch inputs; main/tag pushes do not deploy automatically.
- [x] No deployment was triggered by this configuration work.

## Current blockers verified from the main CI runner

| Setting | State | Evidence / action |
|---|---|---|
| DOCKER_PAT_BACKEND | Present | Masked environment value in Deploy Configuration run |
| DOCKER_PAT_FRONTEND | Present | Masked environment value in Deploy Configuration run |
| DOCKER_USER repository variable | Missing | Set through scripts/configure-github-actions.sh |
| STAGING_SSH_PRIVATE_KEY | Missing | Provide dedicated staging deploy key |
| PRODUCTION_SSH_PRIVATE_KEY | Missing | Provide separate production deploy key |
| STAGING_KNOWN_HOSTS / PRODUCTION_KNOWN_HOSTS | Missing | Supply out-of-band verified pinned host keys |
| STAGING_HOST / STAGING_USER | Missing | Supply actual staging target and non-root deploy account |
| PRODUCTION_HOST / PRODUCTION_USER | Missing | Supply actual production target and non-root deploy account |
| STAGING_DOMAIN / PRODUCTION_DOMAIN | Not configured in the latest runner snapshot | Supply actual HTTPS hostnames |
| Host runtime env files | Not verified | Create separate .env.staging and .env.production on their respective hosts |
| Host Docker Hub pull access | Not verified | Configure read-only credentials on each host |
| Production required reviewer | Not verified | Set explicitly in GitHub Environment if policy requires it |

## Follow-up PR

PR #155 — https://github.com/nyeinpyaesone-ui/ERP/pull/155

Adds:
- Interactive GitHub Actions configuration bootstrapper.
- Staging runtime env template.
- Explicit Docker namespace requirement (removes personal namespace fallbacks).
- Installer validation and CI validation for both Compose templates.

PR #155 must pass its latest CI checks and be reviewed before merge.

## Operator sequence after PR #155 is approved and merged

1. From a trusted workstation, run:
   bash scripts/configure-github-actions.sh
2. Provide actual hostnames, domains, SSH users, dedicated private keys and pinned known_hosts files. The script preserves existing Docker Hub tokens unless replacement is explicitly requested.
3. On each host, provision the matching runtime env file with mode 0600 and configure read-only Docker Hub pull credentials.
4. Verify both images exist for the intended immutable tag.
5. Dispatch CI on main with deploy_staging=true for staging.
6. After staging validation and independent approval, dispatch CI on the v* tag with deploy_production=true for production.

## Safety boundaries

- Staging and production must use separate hosts for the current fixed-name Compose stack.
- Do not use production secrets on staging.
- Do not store runtime secrets in Git, issue comments, chat, or CI logs.
- Do not apply infra/k8s overlays as the production path; GHCR image publishing and cluster deployment are not implemented.
