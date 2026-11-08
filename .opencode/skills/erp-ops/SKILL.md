---
name: ERP Ops
description: CI/CD, secrets and environments contract, blue-green deploys, repo-guard, and host constraints for ERP
---

# ERP Ops

## Active deployment architecture

- Active CI/CD target: Docker Hub images + Docker Compose blue-green on two separate hosts.
- Kubernetes manifests under infra/k8s are a separate scaffold. They reference GHCR image names and have no matching image publish/deploy job. Do not apply them as the active production path.
- Root deploy.sh is legacy. The active workflow calls scripts/deploy-blue-green.sh, which sources scripts/lib.sh.
- The host-local deploy runtime must have its matching .env.staging or .env.production file (mode 0600), plus read-only Docker Hub pull access. Never transfer runtime secrets from GitHub Actions.

## CI contract (.github/workflows/ci.yml)

- Gitleaks → quality (Ruff/Black enforced, MyPy advisory) → PostgreSQL-backed tests → frontend build / image build → Trivy → deploy jobs.
- can_push = DOCKER_USER repository variable + DOCKER_PAT_BACKEND + DOCKER_PAT_FRONTEND.
- can_deploy_staging = can_push + STAGING_SSH_PRIVATE_KEY + STAGING_KNOWN_HOSTS + STAGING_HOST + STAGING_USER.
- can_deploy_production = can_push + PRODUCTION_SSH_PRIVATE_KEY + PRODUCTION_KNOWN_HOSTS + PRODUCTION_HOST + PRODUCTION_USER.
- Missing values are a fail-closed skip, not a successful deployment.
- No push or tag deploys automatically. Dispatch CI on main with deploy_staging=true for staging; dispatch CI on a v* tag with deploy_production=true for production.
- GitHub Environments staging and production constrain deployment refs. The config bootstrapper adds main branch policy and v* tag policy, and refuses unexpected extra policies rather than weakening existing controls.
- All workflow actions remain pinned to full commit SHAs. Gitleaks v3 requires GITHUB_TOKEN on PR scans. Trivy is the only container scanner; do not reintroduce Snyk.

## Configuration workflow

Run bash scripts/configure-github-actions.sh from a trusted operator workstation with gh, jq and ssh-keygen installed and GitHub repository administration / Actions secret-write permissions.

The bootstrapper:
- Sets DOCKER_USER, STAGING_DOMAIN and PRODUCTION_DOMAIN repository variables.
- Sets separate staging/production SSH keys, pinned known_hosts, hosts and users.
- Preserves existing Docker Hub PAT secrets unless an operator explicitly chooses to replace them.
- Ensures staging/main and production/v* Environment deployment-ref policies.
- Refuses root deploy users, shared staging/production hosts, identical SSH keys, and unexpected extra environment policies.
- Does not create server runtime files, connect to servers, or deploy.

## First-deploy blockers

1. Run the configuration bootstrapper using real infrastructure values.
2. Provision separate staging and production hosts with dedicated non-root deploy accounts and correct directory/Docker permissions.
3. Create each host's runtime env file: production via sudo ./install.sh; staging from .env.staging.template with unique values. Set mode 0600.
4. Configure read-only Docker Hub credentials on each host using a credential helper.
5. Add a required reviewer to the production GitHub Environment if independent production approval is required.
6. Verify image tags, host health/readiness, backups and rollback before dispatching a deployment.

## Host constraints and verification

- The original development host is proot/Termux-class aarch64; Docker daemon operations are not reliable there. CI is the verification path for Compose and image builds.
- Run make guard after long jobs and before pushes. Never hardcode file/commit counts in docs.
- Use gh run view <id> --json jobs and fetch job logs to inspect failures; never mark a task complete without tool evidence.
