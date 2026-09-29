# GitHub Secrets & Variables Setup (gh CLI)

Manage this repository's CI/CD configuration with the [GitHub CLI](https://cli.github.com/).

```bash
# Authenticate once (stores token securely in the OS keyring, never in a file)
gh auth login

# Verify authentication and scopes (needs 'repo' + 'admin:repo_hook' to manage secrets)
gh auth status
```

## Required Repository Variables (`gh variable set`)

Variables are **not** secret — use them for non-sensitive config that appears in logs.

| Name | Example Value | Used By |
|------|---------------|---------|
| `DOCKER_USER` | `powerrangeranikg` | CI image naming + Docker Hub login |
| `STAGING_DOMAIN` | `staging.yourdomain.com` | deploy-staging job target URL |
| `PRODUCTION_DOMAIN` | `app.yourdomain.com` | deploy-production job target URL |

```bash
gh variable set DOCKER_USER      --body "powerrangeranikg"
gh variable set STAGING_DOMAIN   --body "staging.yourdomain.com"
gh variable set PRODUCTION_DOMAIN --body "app.yourdomain.com"
```

## Required Repository Secrets (`gh secret set`)

Secrets are encrypted at rest, masked in logs, and only exposed to workflows that reference them.
Never paste real values into issues, PRs, or chat. Pipe from stdin so values don't land in shell history:

```bash
# Docker Hub Personal Access Tokens (create at https://hub.docker.com/settings/security)
echo "<dckr_pat_backend_token>"  | gh secret set DOCKER_PAT_BACKEND
echo "<dckr_pat_frontend_token>" | gh secret set DOCKER_PAT_FRONTEND

# SSH deploy key (private half of a dedicated, passphrase-protected keypair)
gh secret set SSH_PRIVATE_KEY < ~/.ssh/erp_deploy_key

# Deployment targets
echo "staging.example.internal"    | gh secret set STAGING_USER
echo "staging.yourdomain.com"      | gh secret set STAGING_HOST
echo "deploy-admin"                | gh secret set PRODUCTION_USER
echo "prod.yourdomain.com"         | gh secret set PRODUCTION_HOST
# Snyk container scanning (https://app.snyk.io/account)
echo "<snyk-token>" | gh secret set SNYK_TOKEN
```

> Tip: `gh secret set NAME` without input opens an editor prompt — safer than putting the value on the command line.

Verify what is configured (values are never displayed):

```bash
gh secret list
gh variable list
```

## Third-Party Runtime Credentials (server `.env.production`, NOT GitHub)

Application secrets (Stripe, SMTP, OpenAI, DB passwords, `SECRET_KEY`) belong in
`/opt/erp-solution/.env.production` on the deployment server (created by `scripts/setup-production.sh`, mode `600`).
Do **not** duplicate them as GitHub secrets unless a workflow genuinely needs them — CI never requires live payment or email credentials.

## After Setup

Push a tag to trigger build:
```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions will automatically:
- Build backend image
- Build frontend image
- Push both to Docker Hub

## Verify

Check your Docker Hub:
- https://hub.docker.com/r/powerrangeranikg/erp-solution-backend
- https://hub.docker.com/r/powerrangeranikg/erp-solution-frontend

## Security Hygiene

- Rotate Docker PATs and SSH keys every 90 days; revoke immediately if leaked.
- Grant the deploy SSH key least privilege (dedicated user, no root, command-restricted if possible).
- Keep `GITHUB_SECRETS_SETUP.md` free of real tokens — it is committed to the repo.
- Branch protection + required reviews ensure only reviewed code can read these secrets via CI.
