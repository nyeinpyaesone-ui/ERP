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

## 4. Configure GitHub Actions

The repository has a guarded setup script. It validates values before writing
and preserves the existing \`DOCKER_PAT_BACKEND\` and \`DOCKER_PAT_FRONTEND\`
secrets. It creates the \`staging\` and \`production\` GitHub Environments if
missing and adds only the required deployment-ref policies; existing reviewer,
wait-timer, and other environment rules are left unchanged.

First prepare two host-key files on a trusted operator workstation. Obtain the
expected SSH host fingerprints from each hosting provider, compare them with
the scan result, and only then save the verified keys:

\`\`\`bash
ssh-keyscan -H <staging-host> > /secure/path/staging_known_hosts
ssh-keyscan -H <production-host> > /secure/path/production_known_hosts
ssh-keygen -F <staging-host> -f /secure/path/staging_known_hosts
ssh-keygen -F <production-host> -f /secure/path/production_known_hosts
chmod 600 /secure/path/*_known_hosts
\`\`\`

Do not treat \`ssh-keyscan\` itself as authentication; it only collects the key
presented by the network peer. Verify the fingerprint independently before
using the result.

Then configure the repository. Replace the example values with the actual
repository namespace, FQDNs, host addresses, and SSH login users. The script
generates separate Ed25519 keys locally and stores their private halves as
the corresponding GitHub Actions secrets:

\`\`\`bash
bash scripts/configure-github-actions.sh \\
  --repo OWNER/ERP \\
  --docker-user <docker-hub-namespace> \\
  --staging-domain <staging-fqdn> \\
  --production-domain <production-fqdn> \\
  --staging-host <staging-host> \\
  --staging-user <staging-ssh-user> \\
  --production-host <production-host> \\
  --production-user <production-ssh-user> \\
  --staging-known-hosts /secure/path/staging_known_hosts \\
  --production-known-hosts /secure/path/production_known_hosts \\
  --generate-keys \\
  --apply
\`\`\`

Install the two public keys printed by the script into the matching host
accounts' \`~/.ssh/authorized_keys\`. Restrict those accounts and keys to the
deployment directory and the minimum Docker/Compose operations required.
Never copy a staging private key to production or vice versa.

The existing Docker PAT secrets are preserved. If a PAT secret is ever missing,
create separate image-scoped read/write tokens on Docker Hub and supply only
the matching token file with \`--backend-token-file\` or
\`--frontend-token-file\`; do not paste PAT values in chat, shell history, or
repository files.

Validate repository configuration without writing by omitting \`--apply\`.
The script requires the real host/domain values and verified known-host files.
It also requires \`gh\` authenticated to the target repository and \`jq\`
installed.

## 5. Configure runtime hosts

Run the runtime generator once on each dedicated server. Use the exact
hostname/domain that is served by that environment; the generated backend CORS
origin defaults to \`https://app.<domain>\`.

Staging host:

\`\`\`bash
bash scripts/configure-environment.sh \\
  --environment staging \\
  --domain <staging-domain> \\
  --docker-user <docker-hub-namespace> \\
  --version <published-sha-tag> \\
  --dir /opt/erp-solution
\`\`\`

Production host:

\`\`\`bash
bash scripts/configure-environment.sh \\
  --environment production \\
  --domain <production-domain> \\
  --docker-user <docker-hub-namespace> \\
  --version <published-v-tag> \\
  --dir /opt/erp-solution
\`\`\`

The generator refuses to overwrite an existing env file, creates unique
database, Redis, and application secrets, and writes mode \`0600\`. It does not
print the secret values. Back up the files only through your approved encrypted
secret-management process. Both hosts must be separate because the Compose
stack has fixed container names. The application-level \`ENVIRONMENT\` remains
\`prod\` on both hosts; the deploy target chooses the staging or production
configuration file.

Each host also needs read-only Docker Hub credentials so it can pull both
images. Provision a native Docker credential helper first, then run
\`scripts/configure-host-registry.sh\` interactively with a read-only token:

\`\`\`bash
bash scripts/configure-host-registry.sh \\
  --docker-user <docker-hub-namespace> \\
  --image-tag <published-sha-or-v-tag>
\`\`\`

The host script refuses to store a token in Docker's base64-only
\`config.json\`, requires a credential helper, and checks both image manifests.
Use the same namespace and tag that CI published.

## 6. Verification

```bash
gh secret list          # names + updated timestamps (values are never shown)
gh variable list
```

If a required deploy secret is missing, the `Deploy Configuration` job reports
that capability as unavailable and skips the corresponding deploy job. The
SSH step also fails closed if a pinned known-hosts value is unexpectedly empty.
A failed image push usually means a missing/wrong `DOCKER_USER`, a PAT without
write access to its matching repository, or a repository name mismatch.

## 7. GitHub Environments (Settings → Environments)

`ci.yml`'s deploy jobs declare `environment: staging` / `environment: production`.
Both environments must exist, otherwise the jobs fail at the deployment-record
step. Configured policy (created 2026-10-11):

| Environment | Deployment branch policy | Rationale |
|-------------|--------------------------|-----------|
| `staging` | selected branches → `main` only | staging deploys only after explicit manual workflow_dispatch approval on main |
| `production` | selected tags → `v*` only | production deploys only after explicit manual workflow_dispatch approval on a v* tag |

The policies are fail-closed: no other ref can create a deployment. No required reviewers are configured by this setup script. The workflow itself
requires an explicit manual dispatch boolean for each environment; add GitHub
Environment reviewers separately when formal approval is required.

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
