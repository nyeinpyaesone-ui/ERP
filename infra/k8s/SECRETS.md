# Kubernetes runtime secrets

Kubernetes Secret values must not be stored in this repository. The former
`base/secrets.yaml` manifest contained credential-shaped values and has been
removed from the Kustomize resource list. The workloads still reference a
Secret; provision it **before** applying an environment overlay.

## Secret names and namespaces

| Environment | Namespace | Secret name |
|---|---|---|
| Production | `erp_solution` | `erp_solution-secrets` |
| Staging | `erp_solution-staging` | `staging-erp_solution-secrets` |

The staging overlay applies the `staging-` name prefix and changes the
namespace. Confirm rendered names with `kubectl kustomize` before applying.

## Provisioning

Create the environment file outside the repository on a trusted operator
machine. Restrict its permissions (for example, `chmod 600`) and populate it
from the approved secret manager. Do not paste values into shell history,
tickets, chat, CI logs, or Git.

Production:

```bash
kubectl create secret generic erp_solution-secrets \
  --namespace erp_solution \
  --from-env-file=/secure/path/erp-production.env \
  --dry-run=client -o yaml | kubectl apply -f -
```

Staging:

```bash
kubectl create secret generic staging-erp_solution-secrets \
  --namespace erp_solution-staging \
  --from-env-file=/secure/path/erp-staging.env \
  --dry-run=client -o yaml | kubectl apply -f -
```

Then validate the Secret exists without printing its data:

```bash
kubectl -n erp_solution get secret erp_solution-secrets
kubectl -n erp_solution-staging get secret staging-erp_solution-secrets
kubectl kustomize infra/k8s/overlays/staging
kubectl kustomize infra/k8s/overlays/production
```

## Environment keys

The workload Secret contract currently includes:

```text
DB_USER
DB_PASSWORD
DB_URL
REDIS_PASSWORD
REDIS_URL
JWT_SECRET
JWT_REFRESH_SECRET
OPENAI_API_KEY
SENTRY_AUTH_TOKEN
EXPO_ACCESS_TOKEN
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
SMTP_USER
SMTP_PASSWORD
KBZPAY_API_KEY
KBZPAY_MERCHANT_ID
WAVE_API_KEY
WAVE_MERCHANT_ID
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
FACEBOOK_APP_ID
FACEBOOK_APP_SECRET
ENCRYPTION_KEY
SIGNING_KEY
```

Supply values appropriate to each environment. Verify which integrations are
enabled in the application configuration; unused integrations should not be
given production credentials unnecessarily.

## Historical credential exposure

Removing the manifest from the current tree does not remove its values from
earlier Git commits. Treat any value that was ever deployed as exposed:
rotate it in the owning system, update the Kubernetes Secret out-of-band, and
verify consumers have picked up the replacement. Gitleaks scans full history,
so its historical finding remains a release/security gate until the exposure
is remediated. Do not suppress the finding with a broad allowlist.

History rewriting is deliberately excluded from this PR. Coordinate it
separately because it changes commit identities and requires collaborators to
resynchronize their clones.

## Operational requirements

- Enable Kubernetes encryption at rest for Secrets in etcd.
- Restrict Secret read access with least-privilege RBAC.
- Prefer an external secret manager/operator for ongoing synchronization.
- Never commit the environment files; this repository ignores
  `infra/k8s/**/secrets*.env`.
