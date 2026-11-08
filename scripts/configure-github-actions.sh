#!/usr/bin/env bash
# Configure repository Actions variables/secrets and environment ref policies.
# Default mode validates inputs only. Pass --apply to write to GitHub.
set -euo pipefail
umask 077

usage() {
  cat <<'USAGE'
Usage:
  scripts/configure-github-actions.sh [options]

Required:
  --repo OWNER/REPO
  --docker-user NAMESPACE
  --staging-domain FQDN
  --production-domain FQDN
  --staging-host HOST       --staging-user USER
  --production-host HOST   --production-user USER
  --staging-known-hosts FILE
  --production-known-hosts FILE
  --staging-key FILE       --production-key FILE
  --apply

Optional:
  --generate-keys          Generate two new unencrypted Ed25519 deploy keys
                           under --key-dir; public keys are printed at the end.
  --key-dir PATH           Default: ~/.ssh/erp-github-actions-<repo>
  --backend-token-file FILE
  --frontend-token-file FILE
  --opencode-key-file FILE  Optional OpenCode automation secret
  --replace-existing-config Replace existing Actions variables and deploy secrets

Existing Docker PAT secrets are preserved. Supply token files only when a PAT
secret is absent. Host-key files must contain independently verified host keys.
The script creates missing GitHub Environments and adds missing ref policies;
it never removes policies or modifies existing reviewer/approval settings.
USAGE
}

repo=""
docker_user=""
staging_domain=""
production_domain=""
staging_host=""
staging_user=""
production_host=""
production_user=""
staging_known_hosts=""
production_known_hosts=""
staging_key=""
production_key=""
backend_token_file=""
frontend_token_file=""
opencode_key_file=""
replace_existing_config=false
generate_keys=false
apply=false
key_dir=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) repo="$2"; shift 2 ;;
    --docker-user) docker_user="$2"; shift 2 ;;
    --staging-domain) staging_domain="$2"; shift 2 ;;
    --production-domain) production_domain="$2"; shift 2 ;;
    --staging-host) staging_host="$2"; shift 2 ;;
    --staging-user) staging_user="$2"; shift 2 ;;
    --production-host) production_host="$2"; shift 2 ;;
    --production-user) production_user="$2"; shift 2 ;;
    --staging-known-hosts) staging_known_hosts="$2"; shift 2 ;;
    --production-known-hosts) production_known_hosts="$2"; shift 2 ;;
    --staging-key) staging_key="$2"; shift 2 ;;
    --production-key) production_key="$2"; shift 2 ;;
    --backend-token-file) backend_token_file="$2"; shift 2 ;;
    --frontend-token-file) frontend_token_file="$2"; shift 2 ;;
    --opencode-key-file) opencode_key_file="$2"; shift 2 ;;
    --replace-existing-config) replace_existing_config=true; shift ;;
    --generate-keys) generate_keys=true; shift ;;
    --key-dir) key_dir="$2"; shift 2 ;;
    --apply) apply=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

need_value() {
  local name="$1" value="$2"
  [ -n "$value" ] || { echo "Missing required option: $name" >&2; exit 2; }
}
valid_domain() {
  [[ "$1" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]]
}
valid_host() {
  [[ "$1" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] && [[ "$1" != *..* ]]
}
valid_user() {
  [[ "$1" =~ ^[a-z_][a-zA-Z0-9_-]{0,31}$ ]]
}

need_value --repo "$repo"
need_value --docker-user "$docker_user"
need_value --staging-domain "$staging_domain"
need_value --production-domain "$production_domain"
need_value --staging-host "$staging_host"
need_value --staging-user "$staging_user"
need_value --production-host "$production_host"
need_value --production-user "$production_user"
need_value --staging-known-hosts "$staging_known_hosts"
need_value --production-known-hosts "$production_known_hosts"

[[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo "--repo must be OWNER/REPO" >&2; exit 2; }
[[ "$docker_user" =~ ^[a-z0-9][a-z0-9_-]{0,127}$ ]] || { echo "--docker-user must be a lowercase Docker Hub namespace" >&2; exit 2; }
valid_domain "$staging_domain" || { echo "Invalid --staging-domain FQDN" >&2; exit 2; }
valid_domain "$production_domain" || { echo "Invalid --production-domain FQDN" >&2; exit 2; }
valid_host "$staging_host" && valid_host "$production_host" || { echo "Invalid host value" >&2; exit 2; }
valid_user "$staging_user" && valid_user "$production_user" || { echo "SSH users must be valid Unix usernames" >&2; exit 2; }
[ "$staging_host" != "$production_host" ] || { echo "Staging and production must use different hosts" >&2; exit 2; }
[ "$staging_domain" != "$production_domain" ] || { echo "Staging and production must use different domains" >&2; exit 2; }

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v python3 >/dev/null 2>&1 || { echo "python3 is required to validate protected input files" >&2; exit 1; }

validate_secure_file() {
  local label="$1" file="$2"
  python3 - "$label" "$file" "$repo_root" <<'PY'
import os
import stat
import sys

label, path, root = sys.argv[1:]
try:
    info = os.lstat(path)
except OSError as exc:
    print(f"{label}: cannot access input file ({exc})", file=sys.stderr)
    raise SystemExit(1)

if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
    print(f"{label}: input must be a regular, non-symlink file", file=sys.stderr)
    raise SystemExit(1)

resolved = os.path.realpath(path)
root = os.path.realpath(root)
if os.path.commonpath([root, resolved]) == root:
    print(f"{label}: sensitive input files must be stored outside the Git working tree", file=sys.stderr)
    raise SystemExit(1)

if stat.S_IMODE(info.st_mode) & 0o077:
    print(f"{label}: permissions are too broad; set mode 0600", file=sys.stderr)
    raise SystemExit(1)
PY
}

validate_secure_file "Staging known-hosts" "$staging_known_hosts"
validate_secure_file "Production known-hosts" "$production_known_hosts"
[ -s "$staging_known_hosts" ] && [ -s "$production_known_hosts" ] || { echo "Known-hosts files must be non-empty" >&2; exit 2; }
ssh-keygen -F "$staging_host" -f "$staging_known_hosts" >/dev/null || { echo "Staging known-hosts file does not contain $staging_host" >&2; exit 2; }
ssh-keygen -F "$production_host" -f "$production_known_hosts" >/dev/null || { echo "Production known-hosts file does not contain $production_host" >&2; exit 2; }

command -v gh >/dev/null 2>&1 || { echo "GitHub CLI (gh) is required" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 1; }
gh auth status --hostname github.com
gh repo view "$repo" >/dev/null
secret_names="$(gh secret list --repo "$repo" --json name --jq '.[].name')"

if [ "$generate_keys" = true ]; then
  [ -z "$staging_key" ] && [ -z "$production_key" ] || { echo "Use either --generate-keys or provide both key files" >&2; exit 2; }
  [ "$apply" = true ] || { echo "--generate-keys creates local private keys; also pass --apply" >&2; exit 2; }
  slug="${repo//\//-}"
  key_dir="${key_dir:-$HOME/.ssh/erp-github-actions-$slug}"
  mkdir -p "$key_dir"
  key_dir="$(cd "$key_dir" && pwd)"
  case "$key_dir" in
    "$repo_root"|"$repo_root"/*) echo "Refusing to generate private keys inside the Git working tree" >&2; exit 2 ;;
  esac
  chmod 700 "$key_dir"
  staging_key="$key_dir/staging_ed25519"
  production_key="$key_dir/production_ed25519"

  ensure_key_pair() {
    local name="$1" key="$2" comment="$3" secret_name="$4"
    if [ -f "$key" ] && [ -f "$key.pub" ] && [ ! -L "$key" ] && [ ! -L "$key.pub" ]; then
      echo "Reusing existing local $name SSH key pair"
      return 0
    fi
    if [ -e "$key" ] || [ -e "$key.pub" ] || [ -L "$key" ] || [ -L "$key.pub" ]; then
      echo "Incomplete or unsafe $name key pair at $key; refusing to overwrite it." >&2
      exit 1
    fi
    if grep -Fxq "$secret_name" <<< "$secret_names" && [ "$replace_existing_config" != true ]; then
      echo "$secret_name already exists, but its private key is not available locally. Supply the original key file or pass --replace-existing-config with a new key pair." >&2
      exit 1
    fi
    ssh-keygen -q -t ed25519 -N "" -C "$comment" -f "$key"
    chmod 600 "$key"
  }

  ensure_key_pair staging "$staging_key" "erp-staging-github-actions" STAGING_SSH_PRIVATE_KEY
  ensure_key_pair production "$production_key" "erp-production-github-actions" PRODUCTION_SSH_PRIVATE_KEY
fi

need_value --staging-key "$staging_key"
need_value --production-key "$production_key"
[ -s "$staging_key" ] && [ -s "$production_key" ] || { echo "Private key files must exist and be non-empty" >&2; exit 2; }
validate_secure_file "Staging private key" "$staging_key"
validate_secure_file "Production private key" "$production_key"
ssh-keygen -y -P "" -f "$staging_key" >/dev/null
ssh-keygen -y -P "" -f "$production_key" >/dev/null

for required in DOCKER_PAT_BACKEND DOCKER_PAT_FRONTEND; do
  if ! grep -Fxq "$required" <<< "$secret_names"; then
    token_file="$backend_token_file"
    [ "$required" = "DOCKER_PAT_FRONTEND" ] && token_file="$frontend_token_file"
    [ -n "$token_file" ] && [ -s "$token_file" ] || {
      echo "Missing $required. Supply it with --backend-token-file or --frontend-token-file." >&2
      exit 1
    }
  fi
done

for token_file in "$backend_token_file" "$frontend_token_file" "$opencode_key_file"; do
  if [ -n "$token_file" ]; then
    validate_secure_file "Token input file" "$token_file"
    [ -s "$token_file" ] || { echo "Token input files must be non-empty" >&2; exit 2; }
  fi
done

variables_json="$(gh variable list --repo "$repo" --json name,value)"
for item in "DOCKER_USER:$docker_user" "STAGING_DOMAIN:$staging_domain" "PRODUCTION_DOMAIN:$production_domain"; do
  name="${item%%:*}"
  desired="${item#*:}"
  if jq -e --arg name "$name" 'any(.[]; .name == $name)' <<< "$variables_json" >/dev/null; then
    existing="$(jq -r --arg name "$name" '.[] | select(.name == $name) | .value' <<< "$variables_json")"
    if [ "$existing" != "$desired" ] && [ "$replace_existing_config" != true ]; then
      echo "Repository variable $name already exists with a different value. Pass --replace-existing-config to update it." >&2
      exit 1
    fi
  fi
done

if [ "$apply" != true ]; then
  cat <<SUMMARY
Validation passed. No GitHub configuration was changed.
Repository: $repo
Variables to set: DOCKER_USER, STAGING_DOMAIN, PRODUCTION_DOMAIN
Secrets to set: STAGING/PRODUCTION host, user, SSH key, and pinned known_hosts
Docker PAT secrets: preserved if already present
GitHub Environments: staging (main branch), production (v* tags)
Re-run with --apply to configure GitHub.
SUMMARY
  exit 0
fi

set_secret_from_file() {
  local name="$1" file="$2"
  gh secret set "$name" --repo "$repo" < "$file"
}
set_secret_value() {
  local name="$1" value="$2"
  printf '%s' "$value" | gh secret set "$name" --repo "$repo"
}
set_deploy_secret_from_file() {
  local name="$1" file="$2"
  if grep -Fxq "$name" <<< "$secret_names" && [ "$replace_existing_config" != true ]; then
    echo "Preserved existing deployment secret: $name"
    return 0
  fi
  set_secret_from_file "$name" "$file"
}
set_deploy_secret_value() {
  local name="$1" value="$2"
  if grep -Fxq "$name" <<< "$secret_names" && [ "$replace_existing_config" != true ]; then
    echo "Preserved existing deployment secret: $name"
    return 0
  fi
  set_secret_value "$name" "$value"
}
set_repository_variable() {
  local name="$1" value="$2" current
  current="$(jq -r --arg name "$name" '.[] | select(.name == $name) | .value' <<< "$variables_json")"
  if jq -e --arg name "$name" 'any(.[]; .name == $name)' <<< "$variables_json" >/dev/null; then
    if [ "$current" = "$value" ]; then
      echo "Preserved existing repository variable: $name"
      return 0
    fi
    [ "$replace_existing_config" = true ] || { echo "Refusing to replace repository variable $name without --replace-existing-config" >&2; exit 1; }
  fi
  gh variable set "$name" --repo "$repo" --body "$value"
}
ensure_environment() {
  local env_name="$1"
  local environments details
  environments="$(gh api "repos/$repo/environments?per_page=100" --jq '.environments[].name')"

  if ! grep -Fxq "$env_name" <<< "$environments"; then
    gh api --method PUT "repos/$repo/environments/$env_name" \
      -F 'deployment_branch_policy[protected_branches]=false' \
      -F 'deployment_branch_policy[custom_branch_policies]=true' \
      --silent >/dev/null
    echo "Created GitHub Environment with custom deployment-ref policies: $env_name"
    return 0
  fi

  details="$(gh api "repos/$repo/environments/$env_name")"
  if ! jq -e '.deployment_branch_policy.custom_branch_policies == true' <<< "$details" >/dev/null; then
    echo "Environment $env_name already exists but custom deployment-ref policies are disabled." >&2
    echo "Enable custom deployment branch/tag policies in GitHub Settings for this environment, then rerun. Existing reviewer and wait-timer rules were left untouched." >&2
    exit 1
  fi
}
ensure_policy() {
  local env_name="$1" pattern="$2" kind="$3"
  local policies
  policies="$(gh api "repos/$repo/environments/$env_name/deployment-branch-policies?per_page=100")"
  if ! jq -e --arg name "$pattern" --arg type "$kind" 'any((.branch_policies // [])[]; .name == $name and .type == $type)' <<< "$policies" >/dev/null; then
    gh api --method POST "repos/$repo/environments/$env_name/deployment-branch-policies" -f name="$pattern" -f type="$kind" >/dev/null
    echo "Added $kind policy $pattern to $env_name"
  fi
}

# Environment rules are additive; existing reviewer and wait-timer settings are untouched.
ensure_environment staging
ensure_environment production
ensure_policy staging main branch
ensure_policy production 'v*' tag

set_repository_variable DOCKER_USER "$docker_user"
set_repository_variable STAGING_DOMAIN "$staging_domain"
set_repository_variable PRODUCTION_DOMAIN "$production_domain"

set_deploy_secret_value STAGING_HOST "$staging_host"
set_deploy_secret_value STAGING_USER "$staging_user"
set_deploy_secret_from_file STAGING_KNOWN_HOSTS "$staging_known_hosts"
set_deploy_secret_from_file STAGING_SSH_PRIVATE_KEY "$staging_key"
set_deploy_secret_value PRODUCTION_HOST "$production_host"
set_deploy_secret_value PRODUCTION_USER "$production_user"
set_deploy_secret_from_file PRODUCTION_KNOWN_HOSTS "$production_known_hosts"
set_deploy_secret_from_file PRODUCTION_SSH_PRIVATE_KEY "$production_key"

if ! grep -Fxq DOCKER_PAT_BACKEND <<< "$secret_names"; then
  set_secret_from_file DOCKER_PAT_BACKEND "$backend_token_file"
fi
if ! grep -Fxq DOCKER_PAT_FRONTEND <<< "$secret_names"; then
  set_secret_from_file DOCKER_PAT_FRONTEND "$frontend_token_file"
fi
if [ -n "$opencode_key_file" ] && ! grep -Fxq OPENCODE_API_KEY <<< "$secret_names"; then
  set_secret_from_file OPENCODE_API_KEY "$opencode_key_file"
fi

echo "GitHub Actions configuration updated. Secret values were not printed."
if [ "$generate_keys" = true ]; then
  echo "Install these public keys on their matching hosts before deploying:"
  echo "STAGING authorized_keys:"
  cat "$staging_key.pub"
  echo "PRODUCTION authorized_keys:"
  cat "$production_key.pub"
fi
echo "Verify with: gh secret list --repo $repo && gh variable list --repo $repo"
