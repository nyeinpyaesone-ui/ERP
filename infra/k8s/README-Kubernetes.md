# Kubernetes manifests — separate deployment path

## Status

These manifests are **not wired into the current GitHub Actions deployment**.
The CI pipeline builds Docker Hub images for the Docker Compose blue-green
deployment in `docker-compose.prod.yml`. These Kubernetes manifests reference
different GHCR images (`erp_solution-api`, `erp_solution-web`, and
`erp_solution-worker`) and currently have no matching image-publish or
cluster-deploy job.

Do not use this directory as a production deployment runbook until the image
builds, runtime configuration, cluster prerequisites, and operational jobs
have been validated together.

## Repository layout

- `base/` — Kubernetes Deployments, Services, StatefulSets, ConfigMaps,
  RBAC, NetworkPolicy, PVCs, Ingress, and backup CronJob.
- `overlays/development/` — development customization.
- `overlays/staging/` — staging namespace, name prefix, and configuration.
- `overlays/production/` — production customization.
- `monitoring/` — Prometheus manifest.
- `SECRETS.md` — out-of-band Secret names, namespaces, and manifest-backed
  key references.

There is no tracked `base/secrets.yaml` template. Never create or commit one.

## Before any cluster deployment

1. Confirm the intended Kubernetes context and account.
2. Follow [SECRETS.md](SECRETS.md) to create protected environment files.
   Validate them with `scripts/provision-k8s-secrets.sh` using an explicit
   `--context`; add `--apply` only after reviewing the target namespace.
3. Build and publish the exact GHCR images referenced by the manifests.
4. Validate the manifests and their runtime contract against the actual
   container images. In particular, verify container ports, health endpoints,
   ConfigMap keys, Secret keys, storage classes, Ingress/TLS, and service
   accounts.
5. Fix and test the Redis password configuration and backup CronJob image:
   the current Redis ConfigMap contains a shell-style variable expression
   that Redis does not expand, and the current PostgreSQL image does not
   provide the AWS CLI invoked by the backup command.
6. Review the rendered output and cluster diff before applying anything.

## Read-only manifest validation

Run from the repository root:

```bash
kubectl kustomize infra/k8s/overlays/development
kubectl kustomize infra/k8s/overlays/staging
kubectl kustomize infra/k8s/overlays/production
```

After reviewing the rendered output and confirming the current context:

```bash
kubectl config current-context
kubectl diff -k infra/k8s/overlays/staging
kubectl diff -k infra/k8s/overlays/production
```

These commands are validation only. They do not apply resources.
