#!/usr/bin/env bash
# Configure repository-level GitHub Actions variables, secrets and deployment
# environments for the ERP Compose blue/green pipeline.
set -Eeuo pipefail
IFS=$'\n\t'

REPO="${GITHUB_REPOSITORY:-nyeinpyaesone-ui/ERP}"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '==> %s\n' "$*"; }
prompt() {
  local __name="$1" __label="$2" __value=""
  read -r -p "$__label: " __value
  [ -n "$__value" ] || die "$__label is required."
  printf -v "$__name" '%s' "$__value"
}
prompt_file() {
  local __name="$1" __label="$2" __value=""
  read -r -p "$__label (file path): " __value
  [ -f "$__value" ] && [ -r "$__value" ] || die "File is missing or unreadable: $__value"
  [ -s "$__value" ] || die "File is empty: $__value"
  printf -v "$__name" '%s' "$__value"
}
validate_domain() {
  [[ "$1" =~ ^([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$ ]] ||
    die "Expected a DNS hostname without scheme/path: $1"
}
validate_host() {
  [[ "$1" =~ ^([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$ ||
     "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] ||
    die "Expected a hostname or IPv4 address without port: $1"
}
validate_user() {
  [[ "$1" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || die "Invalid SSH username: $1"
  [ "$1" != "root" ] || die "Use a dedicated non-root deployment account."
}
set_secret_file() {
  local key="$1" file="$2"
  info "Setting repository secret $key"
  gh secret set "$key" --repo "$REPO" < "$file"
}
set_secret_value() {
  local key="$1" value="$2"
  info "Setting repository secret $key"
  printf '%s' "$value" | gh secret set "$key" --repo "$REPO"
}
set_variable() {
  local key="$1" value="$2"
  info "Setting repository variable $key"
  gh variable set "$key" --repo "$REPO" --body "$value"
}
ensure_environment_policy() {
  local environment="$1" policy_type="$2" pattern="$3" existing
  info "Ensuring GitHub Environment $environment and $policy_type policy $pattern"
  gh api --method PUT "repos/$REPO/environments/$environment" >/dev/null
  existing="$(gh api "repos/$REPO/environments/$environment/deployment-branch-policies" |
    jq --arg pattern "$pattern" --arg kind "$policy_type" \
    '[.branch_policies[]? | select(.name == $pattern and .type == $kind)] | length')"
  if [ "$existing" = "0" ]; then
    gh api --method POST "repos/$REPO/environments/$environment/deployment-branch-policies" \
      -f name="$pattern" -f type="$policy_type" >/dev/null
  fi
}
command -v gh >/dev/null 2>&1 || die "GitHub CLI (gh) is required."
command -v ssh-keygen >/dev/null 2>&1 || die "ssh-keygen is required."
command -v jq >/dev/null 2>&1 || die "jq is required."
gh auth status --hostname github.com >/dev/null 2>&1 || die "Authenticate gh with repository administration and Actions secrets/variables permissions first."
gh repo view "$REPO" --json nameWithOwner --jq .nameWithOwner | grep -Fx "$REPO" >/dev/null ||
  die "Authenticated GitHub context cannot resolve $REPO."

printf '\nERP GitHub Actions configuration\nRepository: %s\n\n' "$REPO"
printf 'This configures GitHub repository settings only. It does not connect to or deploy to either server.\n'
printf 'Have the approved SSH keys, pinned known_hosts files and Docker Hub tokens ready.\n\n'

DOCKER_USER="${DOCKER_USER:-powerrangeranikg}"
read -r -p "Docker Hub namespace [$DOCKER_USER]: " input
DOCKER_USER="${input:-$DOCKER_USER}"
[[ "$DOCKER_USER" =~ ^[a-z0-9][a-z0-9_-]{0,127}$ ]] || die "Invalid Docker Hub namespace."

prompt STAGING_DOMAIN "Staging deployment URL hostname"
validate_domain "$STAGING_DOMAIN"
prompt PRODUCTION_DOMAIN "Production deployment URL hostname"
validate_domain "$PRODUCTION_DOMAIN"
prompt STAGING_HOST "Staging SSH hostname/IP"
validate_host "$STAGING_HOST"
prompt STAGING_USER "Staging SSH username"
validate_user "$STAGING_USER"
prompt PRODUCTION_HOST "Production SSH hostname/IP"
validate_host "$PRODUCTION_HOST"
prompt PRODUCTION_USER "Production SSH username"
validate_user "$PRODUCTION_USER"

[ "$STAGING_HOST" != "$PRODUCTION_HOST" ] || die "Staging and production must be separate hosts for the current fixed-name Compose stack."
[ "$STAGING_DOMAIN" != "$PRODUCTION_DOMAIN" ] || die "Staging and production deployment domains must be different."

prompt_file BACKEND_TOKEN_FILE "Docker Hub backend push token file"
prompt_file FRONTEND_TOKEN_FILE "Docker Hub frontend push token file"
prompt_file STAGING_KEY_FILE "Staging deploy private key"
prompt_file PRODUCTION_KEY_FILE "Production deploy private key"
prompt_file STAGING_KNOWN_HOSTS_FILE "Pinned staging known_hosts file"
prompt_file PRODUCTION_KNOWN_HOSTS_FILE "Pinned production known_hosts file"

# The current ssh-agent workflow does not accept passphrases. Require dedicated,
# unencrypted deploy keys with narrow host-account permissions.
ssh-keygen -y -P '' -f "$STAGING_KEY_FILE" >/dev/null 2>&1 ||
  die "Staging key must be a valid unencrypted private key."
ssh-keygen -y -P '' -f "$PRODUCTION_KEY_FILE" >/dev/null 2>&1 ||
  die "Production key must be a valid unencrypted private key."
ssh-keygen -F "$STAGING_HOST" -f "$STAGING_KNOWN_HOSTS_FILE" >/dev/null ||
  die "Pinned staging known_hosts file has no matching entry for $STAGING_HOST."
ssh-keygen -F "$PRODUCTION_HOST" -f "$PRODUCTION_KNOWN_HOSTS_FILE" >/dev/null ||
  die "Pinned production known_hosts file has no matching entry for $PRODUCTION_HOST."

# Configure repo variables and secrets. Secret contents are read from protected
# files or piped through stdin; they are never printed or placed in argv.
set_variable DOCKER_USER "$DOCKER_USER"
set_variable STAGING_DOMAIN "$STAGING_DOMAIN"
set_variable PRODUCTION_DOMAIN "$PRODUCTION_DOMAIN"
set_secret_file DOCKER_PAT_BACKEND "$BACKEND_TOKEN_FILE"
set_secret_file DOCKER_PAT_FRONTEND "$FRONTEND_TOKEN_FILE"
set_secret_file STAGING_SSH_PRIVATE_KEY "$STAGING_KEY_FILE"
set_secret_file PRODUCTION_SSH_PRIVATE_KEY "$PRODUCTION_KEY_FILE"
set_secret_file STAGING_KNOWN_HOSTS "$STAGING_KNOWN_HOSTS_FILE"
set_secret_file PRODUCTION_KNOWN_HOSTS "$PRODUCTION_KNOWN_HOSTS_FILE"
set_secret_value STAGING_HOST "$STAGING_HOST"
set_secret_value STAGING_USER "$STAGING_USER"
set_secret_value PRODUCTION_HOST "$PRODUCTION_HOST"
set_secret_value PRODUCTION_USER "$PRODUCTION_USER"

# Current CI deploy jobs require these environments. Restrict refs to the
# intended branch/tag; production reviewer protection is configured separately
# by an administrator because reviewer identity must be explicitly selected.
ensure_environment_policy staging branch main
ensure_environment_policy production tag 'v*'

info "Configuration written. Verify names only; secret values are never returned:"
gh secret list --repo "$REPO"
gh variable list --repo "$REPO"
info "GitHub Actions settings configured. No deployment was triggered."
