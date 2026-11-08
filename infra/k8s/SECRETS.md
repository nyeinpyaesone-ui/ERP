# Kubernetes runtime secrets

Kubernetes Secret values must not be stored in this repository. The former
`base/secrets.yaml` manifest contained credential-shaped values and has been
removed from the Kustomize resource list. The workloads still reference a
Secret; provision it **before** applying an environment overlay.

## Secret names and namespaces

| Environment | Namespace | Secret name |
|---|---|---|
| Production | `erp-solution` | `erp-solution-secrets` |
| Staging | `erp-solution-staging` | `staging-erp-solution-secrets` |

The staging overlay applies the `staging-` name prefix and changes the
namespace. Kustomize also rewrites the workload `secretRef` name, so the
staging Secret must be named `staging-erp-solution-secrets`. Confirm rendered
names with `kubectl kustomize` before applying.

## Provisioning

Use `infra/k8s/secrets.env.template` only as a key-name reference; it contains
placeholders and must never be applied. Create the real environment file
outside the repository on a trusted operator machine. Restrict its permissions
(`chmod 600`) and populate it from the approved secret manager. The provisioner
rejects `REPLACE_WITH_*` and other placeholder values. Do not paste values into
shell history, tickets, chat, CI logs, or Git.

Required keys are taken from the current base manifest's explicit
`secretKeyRef` entries:

- `DB_USER`
- `DB_PASSWORD`
- `REDIS_PASSWORD`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

The Secret is provisioned by `scripts/provision-k8s-secrets.sh`. It defaults
to validation-only mode, requires an explicit Kubernetes context, refuses
files inside the repository or with group/other permissions, and never prints
Secret data.

The environment overlays now use DNS-compatible namespaces and Secret
names:

| Environment | Namespace | Secret |
|---|---|---|
| Development | `erp-solution-dev` | not provisioned by this script |
| Staging | `erp-solution-staging` | `staging-erp-solution-secrets` |
| Production | `erp-solution` | `erp-solution-secrets` |

Validate the Secret input and intended context first. With
`--create-namespace`, the script reports the namespace it would create but
does not change the cluster in validation mode:

```bash
bash scripts/provision-k8s-secrets.sh \
  --environment production \
  --context <production-context> \
  --file /secure/path/erp-production.env \
  --create-namespace
```

Apply only after reviewing the context, namespace, and Secret target. The
explicit `--apply --create-namespace` flags create the namespace if missing
and then create the Secret. Existing Secret data is not replaced unless
`--replace-existing` is also supplied:

```bash
bash scripts/provision-k8s-secrets.sh \
  --environment production \
  --context <production-context> \
  --file /secure/path/erp-production.env \
  --create-namespace \
  --apply
```

For staging, use `--environment staging`, the staging cluster context, and
the staging-specific env file. The provisioner has no development mapping;
do not reuse staging or production Secret values in development.

Verify only the Secret metadata (not its data) and render both overlays:

```bash
kubectl --context <production-context> -n erp-solution get secret erp-solution-secrets
kubectl --context <staging-context> -n erp-solution-staging get secret staging-erp-solution-secrets
kubectl kustomize infra/k8s/overlays/staging
kubectl kustomize infra/k8s/overlays/production
```

## Keys explicitly referenced by the Kubernetes manifests

These keys are referenced through `secretKeyRef` in the current base
manifests:

| Secret key | Workload references |
|---|---|
| `DB_USER` | PostgreSQL StatefulSet and backup CronJob |
| `DB_PASSWORD` | PostgreSQL StatefulSet and backup CronJob |
| `REDIS_PASSWORD` | Redis StatefulSet and backup CronJob |
| `AWS_ACCESS_KEY_ID` | Backup CronJob |
| `AWS_SECRET_ACCESS_KEY` | Backup CronJob |

The API and worker Deployments use `envFrom.secretRef`, which exposes every
key present in the Secret to those containers. The manifest does not define a
complete application-level environment contract for those images; add further
keys only after checking the exact image's configuration. The old removed
template listed many `REPLACE_WITH_*` names that are not direct
`secretKeyRef` requirements in these manifests.

`S3_BUCKET` is read from the Kubernetes ConfigMap, not this Secret. The
Kubernetes manifests are a separate deployment path from the current
GitHub Actions Docker Compose deployment; CI does not build or publish the
GHCR image names referenced by these manifests.

## Historical credential exposure

The two Gitleaks findings in commit
`74235a961c917cc3de6e23a8c0480eedb24fd6c9` were verified as
`REPLACE_WITH_32_BYTE_KEY` template placeholders, not live credentials.
The root `.gitleaks.toml` allowlist is deliberately constrained to that
single commit, file path, and exact placeholder value. It does not suppress
other findings or future secrets.

The deleted manifest's other values were also `REPLACE_WITH_*` templates.
No credential rotation is indicated by these specific findings. If an
operator ever replaced a template with a real credential and committed that
value, rotate it in the owning system and update Kubernetes out-of-band.

History rewriting is not needed for these verified placeholders and is
deliberately excluded from this PR.

## Operational requirements

- Enable Kubernetes encryption at rest for Secrets in etcd.
- Restrict Secret read access with least-privilege RBAC.
- Prefer an external secret manager/operator for ongoing synchronization.
- Never commit the environment files; this repository ignores
  `infra/k8s/**/secrets*.env`.
