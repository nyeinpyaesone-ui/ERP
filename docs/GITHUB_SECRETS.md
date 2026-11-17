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

No secret is needed. Container scanning runs via **Trivy** inside `ci.yml`
(the `security` job, gated on the Docker Hub push capability) and uploads
SARIF to GitHub code scanning. The former `snyk-container.yml` workflow and
its `SNYK_TOKEN` dependency were removed — Trivy is the only container
scanner.

### Automation

| Secret | Used by | Notes |
|--------|---------|-------|
| `OPENCODE_API_KEY` | `opencode.yml` | Only `MEMBER` / `OWNER` / `COLLABORATOR` comments can trigger this job |

## 2. Repository variables (Settings → Secrets and variables → **Variables**)

Variables are not secret — they are safe to read in logs and to use in
`if:` conditions.

| Variable | Used by | Value |
|----------|---------|-------|
| `DOCKER_USER` | `ci.yml`, `release.yml` | Docker Hub namespace, e.g. `powerrangeranikg` |
| `STAGING_DOMAIN` | `deploy-staging` | Staging hostname for deployment links |
| `PRODUCTION_DOMAIN` | `deploy-production` | Production hostname for deployment links |

If `DOCKER_USER` is unset, `docker/metadata-action` receives an empty `images`
value and the `docker-*` jobs fail at the push step.

## 3. Optional — runtime only, not referenced by CI

These belong in a deployed server's `.env` (see `docs/PRODUCTION_DEPLOYMENT.md`),
not in GitHub Actions secrets. Written from what `backend/app/config.py`
actually declares — verify against `Settings` before trusting a row:

| Variable | Purpose | Wiring status |
|----------|---------|---------------|
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_PUBLISHABLE_KEY` | Billing (PaymentIntents + webhook) | Wired in `routers/payments.py`; returns HTTP 400 "not configured" until set |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Local LLM inference | Wired in `services/llm_service.py`; defaults to `http://localhost:11434` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | Outbound email | **Declared but unwired** — no mail-sending service exists yet; safe to leave at defaults |
| `SENTRY_DSN` | Error tracking | **Not read** — no Sentry SDK is a dependency |
| `OPENAI_API_KEY` | Hosted-LLM alternative | **Not read** — only Ollama is implemented |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S3-compatible object storage | **Not read** — uploads go to local `UPLOAD_DIR`; no boto3 installed |

Frontend: the browser bundle reads `VITE_API_URL` at build time
(see `backend/frontend-react/.env.example`); unset means same-origin
`/api/v1`, which is correct for the packaged nginx setup.

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

## 6. GitHub Environments (Settings → Environments)

`ci.yml`'s deploy jobs declare `environment: staging` / `environment: production`.
Both environments must exist, otherwise the jobs fail at the deployment-record
step. Configured policy (created 2026-10-11):

| Environment | Deployment branch policy | Rationale |
|-------------|--------------------------|-----------|
| `staging` | selected branches → `main` only | staging deploys on every push to main |
| `production` | selected tags → `v*` only | production deploys only from release tags |

The policies are fail-closed: no other ref can create a deployment. No
required reviewers are configured — deploys are automated blue-green; add a
reviewer rule here if human approval is ever wanted (the job will pause
waiting for it).

The `copilot` environment is auto-created by GitHub Copilot's coding agent —
leave it alone. Do not create environments named after tools (`Docker` etc.);
nothing references them.

```bash
gh api repos/OWNER/ERP/environments --jq '.environments[].name'
gh api repos/OWNER/ERP/environments/staging/deployment-branch-policies
gh api repos/OWNER/ERP/environments/production/deployment-branch-policies
```

## Related

- `.github/workflows/ci.yml` — gate and deploy graph
- `.github/workflows/release.yml` — tag → verify images → GitHub Release
- `docs/BLUE_GREEN_DEPLOYMENT.md` — what the deploy jobs execute
- `docs/BACKUP_RESTORE.md` — `scripts/backup.sh` uses `DB_PASSWORD` locally
