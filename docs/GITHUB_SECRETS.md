# GitHub Actions Secrets Setup

Every secret below is read by a workflow in `.github/workflows/`. Names were
taken from the workflow files, not from memory — if a workflow references a
secret that is missing here, the workflow is the source of truth.

Go to **Settings → Secrets and variables → Actions**.

## 1. Secrets (Settings → Secrets → Actions)

### Docker Hub — image push

| Secret | Used by | Notes |
|--------|---------|-------|
| `DOCKER_PAT_BACKEND` | `ci.yml` → `docker-backend` | Access token scoped to `powerrangeranikg/erp-solution-backend` |
| `DOCKER_PAT_FRONTEND` | `ci.yml` → `docker-frontend` | Access token scoped to `powerrangeranikg/erp-solution-frontend` |

The username is **not** a secret — it is the `DOCKER_USER` repository variable
(see §2). Separate tokens per image keep a frontend-only push from being able
to overwrite the backend image.

Generate a token at <https://hub.docker.com/settings/access/tokens>.

### SSH deploys — `ci.yml` deploy jobs

| Secret | Used by | Notes |
|--------|---------|-------|
| `SSH_PRIVATE_KEY` | `deploy-staging`, `deploy-production` | Deploy key, not your personal key |
| `STAGING_USER` | `deploy-staging` | SSH user on the staging host |
| `STAGING_HOST` | `deploy-staging` | Staging hostname or IP |
| `STAGING_KNOWN_HOSTS` | `deploy-staging` | **Required.** Pinned host keys |
| `PRODUCTION_USER` | `deploy-production` | SSH user on the production host |
| `PRODUCTION_HOST` | `deploy-production` | Production hostname or IP |
| `PRODUCTION_KNOWN_HOSTS` | `deploy-production` | **Required.** Pinned host keys |

Host-key note — the workflows previously ran `ssh-keyscan` at deploy time.
`ssh-keyscan` performs **no authentication**: whatever answers the TCP
connection supplies the key, so a machine that intercepts DNS or port 22 can
substitute its own key and receive your SSH traffic. The workflows now read
pinned keys from these secrets and **fail closed** if a secret is empty, which
means an unset `*_KNOWN_HOSTS` blocks the deploy rather than silently trusting
any key. Populate each one once, out of band:

```bash
# Run this once per host from a trusted machine; review the fingerprint first
# (compare it with your provider's published fingerprint) before committing it.
ssh-keyscan -H staging.example.com > /tmp/staging_known_hosts
ssh-keyscan -H erp.example.com   > /tmp/production_known_hosts
```

Then add them as secrets (see §4). Rotate if a host key ever changes.

### Security scanning

| Secret | Used by | Notes |
|--------|---------|-------|
| `SNYK_TOKEN` | `snyk-container.yml` | <https://snyk.io> → account settings |

`SNYK_TOKEN` steps are `continue-on-error: true`, so a missing token degrades
to "no findings reported" rather than a red build. Treat an empty token as an
absent scanner, not a clean result.

### Automation

| Secret | Used by | Notes |
|--------|---------|-------|
| `OPENCODE_API_KEY` | `opencode.yml` | Only `MEMBER` / `OWNER` / `COLLABORATOR` comments can trigger this job |

## 2. Repository variables (Settings → Secrets and variables → **Variables**)

Variables are not secret — they are safe to read in logs and to use in
`if:` conditions.

| Variable | Used by | Value |
|----------|---------|-------|
| `DOCKER_USER` | `ci.yml`, `snyk-container.yml`, `release.yml` | Docker Hub namespace, e.g. `powerrangeranikg` |
| `STAGING_DOMAIN` | `deploy-staging` | Staging hostname for deployment links |
| `PRODUCTION_DOMAIN` | `deploy-production` | Production hostname for deployment links |

If `DOCKER_USER` is unset, `docker/metadata-action` receives an empty `images`
value and the `docker-*` jobs fail at the push step.

## 3. Optional — runtime only, not referenced by CI

These belong in a deployed server's `.env` (see `docs/PRODUCTION_DEPLOYMENT.md`),
not in GitHub Actions secrets. Listed because `config.py` reads them.

| Variable | Purpose |
|----------|---------|
| `STRIPE_SECRET_KEY` | Billing webhooks |
| `SENTRY_DSN` | Error tracking |
| `OPENAI_API_KEY` | Optional hosted-LLM alternative to Ollama |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S3-compatible object storage for uploads |

## 4. Setting secrets

```bash
gh auth login

gh secret set DOCKER_PAT_BACKEND < token.txt
gh secret set STAGING_KNOWN_HOSTS < /tmp/staging_known_hosts
gh variable set DOCKER_USER --body "powerrangeranikg"
```

## 5. Verification

```bash
gh secret list          # names + updated timestamps (values are never shown)
gh variable list
```

For a missing secret, the deploy jobs now fail with an explicit
`::error::STAGING_KNOWN_HOSTS secret is empty` message rather than a
cryptic SSH error. A failed image push almost always means `DOCKER_USER` or one
of the `DOCKER_PAT_*` tokens.

## Related

- `.github/workflows/ci.yml` — gate and deploy graph
- `.github/workflows/release.yml` — tag → verify images → GitHub Release
- `docs/BLUE_GREEN_DEPLOYMENT.md` — what the deploy jobs execute
- `docs/BACKUP_RESTORE.md` — `scripts/backup.sh` uses `DB_PASSWORD` locally
