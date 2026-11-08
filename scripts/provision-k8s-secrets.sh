#!/usr/bin/env bash
# Provision the Kubernetes Secret required by the separate infra/k8s scaffold.
# Defaults to validation only; --apply is required to write to a cluster.
set -euo pipefail
umask 077

usage() {
  cat <<'USAGE'
Usage:
  scripts/provision-k8s-secrets.sh --environment staging|production --context CONTEXT --file /secure/path/secrets.env [--apply] [--replace-existing]

Mappings:
  production: namespace erp_solution, Secret erp_solution-secrets
  staging:    namespace erp_solution-staging, Secret staging-erp_solution-secrets

The file must be outside the repository and mode 0600. Required keys:
  DB_USER, DB_PASSWORD, REDIS_PASSWORD, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

Dry-run validation is the default. --apply creates or updates the Secret;
--replace-existing is additionally required to update an existing Secret.
The script never prints Secret data or changes the current kubectl context.
USAGE
}

environment=""
context=""
secret_file=""
apply=false
replace_existing=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --environment) environment="$2"; shift 2 ;;
    --context) context="$2"; shift 2 ;;
    --file) secret_file="$2"; shift 2 ;;
    --apply) apply=true; shift ;;
    --replace-existing) replace_existing=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$environment" in
  production) namespace="erp_solution"; secret_name="erp_solution-secrets" ;;
  staging) namespace="erp_solution-staging"; secret_name="staging-erp_solution-secrets" ;;
  *) echo "--environment must be staging or production" >&2; exit 2 ;;
esac
[ -n "$context" ] || { echo "--context is required; do not rely on the current context" >&2; exit 2; }
[ -n "$secret_file" ] && [ -f "$secret_file" ] || { echo "--file must reference an existing secret env file" >&2; exit 2; }
[ ! -L "$secret_file" ] || { echo "Secret env file must not be a symlink" >&2; exit 2; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl is required" >&2; exit 1; }
command -v stat >/dev/null 2>&1 || { echo "stat is required" >&2; exit 1; }

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
secret_real="$(cd "$(dirname "$secret_file")" && pwd)/$(basename "$secret_file")"
case "$secret_real" in
  "$repo_root"|"$repo_root"/*) echo "Secret env files must be stored outside the repository" >&2; exit 2 ;;
esac

mode="$(stat -c '%a' "$secret_file")"
if [[ ! "$mode" =~ ^[0-7]{3,4}$ ]] || (( (8#$mode & 077) != 0 )); then
  echo "Secret env file permissions are too broad; run chmod 600 on it" >&2
  exit 2
fi

has_value() {
  local key="$1"
  awk -F= -v wanted="$key" '$1 == wanted && index($0, "=") > 0 && length(substr($0, index($0, "=") + 1)) > 0 { found=1 } END { exit !found }' "$secret_file"
}
missing=()
for key in DB_USER DB_PASSWORD REDIS_PASSWORD AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do
  has_value "$key" || missing+=("$key")
done
if [ "${#missing[@]}" -gt 0 ]; then
  echo "Missing non-empty required keys in secret env file: ${missing[*]}" >&2
  exit 2
fi

current_context="$(kubectl config current-context 2>/dev/null || true)"
if [ -z "$current_context" ]; then
  echo "No current kubectl context is configured; refusing to continue" >&2
  exit 1
fi
kubectl --context "$context" get namespace "$namespace" >/dev/null

existing="$(kubectl --context "$context" --namespace "$namespace" get secret "$secret_name" --ignore-not-found -o name)"
if [ -n "$existing" ] && [ "$apply" = true ] && [ "$replace_existing" != true ]; then
  echo "Secret already exists. Review ownership before updating; pass --replace-existing to allow an update." >&2
  exit 1
fi
if [ "$replace_existing" = true ] && [ "$apply" != true ]; then
  echo "--replace-existing requires --apply" >&2
  exit 2
fi

kubectl --context "$context" --namespace "$namespace" create secret generic "$secret_name" \
  --from-env-file="$secret_file" --dry-run=client -o name >/dev/null

if [ "$apply" = true ]; then
  kubectl --context "$context" --namespace "$namespace" create secret generic "$secret_name" \
    --from-env-file="$secret_file" --dry-run=client -o yaml |
    kubectl --context "$context" apply -f - >/dev/null
  echo "Provisioned Secret $namespace/$secret_name on context $context."
else
  echo "Validated $namespace/$secret_name on context $context; no cluster changes made."
  echo "Run again with --apply to create the Secret."
fi
