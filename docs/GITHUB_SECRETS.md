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
| `STAGING_SSH_PRIVATE_KEY` | `deploy-staging` | Staging-only deploy key |
| `PRODUCTION_SSH_PRIVATE_KEY` | `deploy-production` | Production-only deploy key |
| `STAGING_USER` | `deploy-staging` | SSH user on the staging host |
| `STAGING_HOST` | `deploy-staging` | Staging hostname or IP |
| `STAGING_KNOWN_HOSTS` | `deploy-staging` | **Required.** Pinned host keys |
| `PRODUCTION_USER` | `deploy-production` | SSH user on the production host |
| `PRODUCTION_HOST` | `deploy-production` | Production hostname or IP |
| `PRODUCTION_KNOWN_HOSTS` | `deploy-production` | **Required.** Pinned host keys |

Environment isolation — use separate staging and production SSH keys. **These secrets must currently be repository-level Actions secrets** because the `config` job detects their presence before either deploy job starts; environment-scoped secrets are not visible to that detector. The deploy jobs still use the `staging` and `production` GitHub Environments for branch/tag policies and any configured approval rules. Neither a main push nor a release-tag push deploys automatically: operators must manually dispatch `CI` with `deploy_staging=true` on `main` or `deploy_production=true` on a `v*` tag.

Remote registry access — the deploy workflow pulls both Docker Hub images on the target host over SSH. Provision a read-only Docker Hub credential on each host (`docker login` for the configured namespace) and verify it can pull both `erp-solution-backend` and `erp-solution-frontend`. CI push tokens are not sent to the servers.

Target host runtime — each host needs its own `/opt/erp-solution/.env.staging` or `.env.production` file (mode `0600`), created from `.env.production.template` but populated with that environment's independent database, Redis, and application secrets. Keep the application setting `ENVIRONMENT=prod` (the backend accepts `dev|test|prod`); staging is selected by the deployment target and its separate `.env.staging` values. The deploy script selects `.env.staging` for staging and `.env.production` for production; it fails closed if the matching file is absent. Never use production credentials on staging. The two environments must use separate hosts because the Compose stack has fixed container names. The workflow syncs the deployment script, Compose file, and static blue/green upstream templates from the exact CI revision. It preserves env files, TLS material, the runtime-managed `nginx/ssl.conf`, persistent data, and `nginx/upstream-active.conf`.

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

If `DOCKER_USER` or either Docker Hub push token is unset, images are built locally under the non-published `local` namespace and are not pushed; deploy jobs are skipped. `DOCKER_USER` must be a lowercase Docker Hub namespace. Staging deploys the immutable `sha-*` tag from that build by default. Production deploys the version tag (`v*`).

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

## 4. Provisioning repository settings

The repository includes an interactive bootstrapper that validates host/key
inputs, sets the variables and secrets listed above, and creates the `staging`
and `production` GitHub Environments with `main` and `v*` deployment-ref
policies. It reads secret values from local files/stdin; it does not print them.
Run it from a trusted operator workstation after authenticating `gh` with
repository administration and Actions secret/variable permissions:

```bash
gh auth login
bash scripts/configure-github-actions.sh
```

The script asks for the actual domains, hostnames, SSH users, token-file paths,
private-key paths, and pinned `known_hosts` paths. It defaults the Docker Hub
namespace to `powerrangeranikg` (confirm it at the prompt). It refuses shared
staging/production hosts and requires unencrypted dedicated SSH keys because
the current ssh-agent workflow has no passphrase input. Verify host key
fingerprints out-of-band before providing the `known_hosts` files.

For manual or non-interactive setup, the equivalent commands are:

```bash

gh secret set DOCKER_PAT_BACKEND < /secure/path/docker-backend-push-token.txt
gh secret set DOCKER_PAT_FRONTEND < /secure/path/docker-frontend-push-token.txt
gh secret set STAGING_SSH_PRIVATE_KEY < /secure/path/staging_deploy_key
gh secret set PRODUCTION_SSH_PRIVATE_KEY < /secure/path/production_deploy_key
gh secret set STAGING_KNOWN_HOSTS < /secure/path/staging_known_hosts
gh secret set PRODUCTION_KNOWN_HOSTS < /secure/path/production_known_hosts
gh secret set STAGING_HOST --body "<staging-host>"
gh secret set STAGING_USER --body "<staging-user>"
gh secret set PRODUCTION_HOST --body "<production-host>"
gh secret set PRODUCTION_USER --body "<production-user>"
gh variable set DOCKER_USER --body "<docker-hub-namespace>"
```

## 5. Target-host runtime configuration

The GitHub bootstrapper does not log in to servers or create runtime files.
On each isolated host, create the matching environment file with mode `0600`.
Production is generated by `sudo ./install.sh <domain> <email>`; the installer
prompts for the Docker Hub namespace and generates unique database, Redis, and
application secrets. For staging, copy `.env.staging.template` to
`/opt/erp-solution/.env.staging`, replace every `CHANGE_ME_*` value using the
approved secret manager or `openssl rand`, set the real staging CORS origin and
Docker namespace, and enforce `chmod 600`. Never copy production values into
staging.

Each target host also needs a Docker Hub **read-only** token for the two image
repositories so the remote deploy script can pull images. Store it using the
host's configured Docker credential helper; do not put it in the runtime env
file or CI logs. The CI push tokens are not transferred to hosts.

## 6. Verification

```bash
gh secret list          # names + updated timestamps (values are never shown)
gh variable list
```

If a required deploy secret is missing, the `Deploy Configuration` job reports
that capability as unavailable and skips the corresponding deploy job. The
SSH step also fails closed if a pinned known-hosts value is unexpectedly empty.
A failed image push almost always means `DOCKER_USER` or one of the
`DOCKER_PAT_*` tokens.

## 7. GitHub Environments (Settings → Environments)

`ci.yml`'s deploy jobs declare `environment: staging` / `environment: production`.
Both environments must exist, otherwise the jobs fail at the deployment-record
step. Configured policy (created 2026-10-11):

| Environment | Deployment branch policy | Rationale |
|-------------|--------------------------|-----------|
| `staging` | selected branches → `main` only | staging deploy is an explicit workflow dispatch on main |
| `production` | selected tags → `v*` only | production deploy is an explicit workflow dispatch on a release tag |

The policies are fail-closed: no other ref can create a deployment. No required reviewers are configured by the bootstrapper because reviewer
identities must be selected by a repository administrator. Add at least one
required reviewer to the `production` environment before enabling production
deploys if your release policy requires independent approval.

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
