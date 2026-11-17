# GitHub Actions Configuration

The authoritative configuration contract is in docs/GITHUB_SECRETS.md.

## Recommended setup

From a trusted operator workstation, authenticate GitHub CLI with repository
administration and Actions secret/variable permissions, then run:

```bash
gh auth login
bash scripts/configure-github-actions.sh
```

Requirements: gh, jq, and ssh-keygen.

The bootstrapper configures:
- Repository variables: DOCKER_USER, STAGING_DOMAIN, PRODUCTION_DOMAIN.
- Existing Docker Hub push secrets are preserved unless explicitly replaced.
- Separate staging/production SSH private keys and pinned known_hosts.
- Staging/production SSH host and non-root user secrets.
- GitHub Environments with main and v* deployment-ref policies.

It prompts for real infrastructure values and local file paths. Never paste
tokens or private keys into chat, source files, issue comments, or terminal
arguments. Verify host key fingerprints out-of-band before supplying
known_hosts files.

## Current CI/CD behavior

- A push to main builds/tests; it does not automatically deploy.
- Staging requires manual CI dispatch on main with deploy_staging=true.
- Production requires manual CI dispatch on a v* tag with
  deploy_production=true.
- The target hosts also need separate runtime env files and read-only Docker
  Hub pull credentials. GitHub Actions secrets do not replace host runtime
  configuration.

Verify names only:

```bash
gh secret list --repo nyeinpyaesone-ui/ERP
gh variable list --repo nyeinpyaesone-ui/ERP
```

See docs/PRODUCTION_DEPLOYMENT.md and infra/k8s/SECRETS.md for the separate
runtime paths.
