#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — GitHub Secrets & Variables Configurator
#
# Applies the repository configuration required by .github/workflows/ci.yml,
# snyk-container.yml and codeql.yml using the GitHub CLI (`gh`).
#
# Usage:
#   ./scripts/configure-gh-secrets.sh            # apply everything missing
#   ./scripts/configure-gh-secrets.sh --list     # show what is configured
#   ./scripts/configure-gh-secrets.sh --check    # report gaps only (exit 1 if missing)
#
# Values are NEVER stored in this file or in shell history:
#   - Non-sensitive variables come from arguments / prompts.
#   - Secret values are read interactively via `gh secret set` (editor prompt)
#     or piped from stdin / files at runtime.
###############################################################################

set -euo pipefail

REPO="${GH_REPO:-nyeinpyaesone-ui/ERP}"

# --- What the workflows reference (source of truth: grep of .github/workflows) ---
REQUIRED_VARIABLES=(DOCKER_USER STAGING_DOMAIN PRODUCTION_DOMAIN)
REQUIRED_SECRETS=(
  DOCKER_PAT_BACKEND
  DOCKER_PAT_FRONTEND
  SSH_PRIVATE_KEY
  STAGING_USER
  STAGING_HOST
  PRODUCTION_USER
  PRODUCTION_HOST
  SNYK_TOKEN
)

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; }

require_gh() {
  command -v gh >/dev/null 2>&1 || { err "GitHub CLI not found. Install: https://cli.github.com/"; exit 1; }
  gh auth status >/dev/null 2>&1 || { err "Not authenticated. Run: gh auth login"; exit 1; }
}

existing_variables() { gh variable list --repo "$REPO" --json name -q '.[].name' 2>/dev/null || true; }
existing_secrets()   { gh secret list   --repo "$REPO" --json name -q '.[].name' 2>/dev/null || true; }

list_current() {
  require_gh
  info "Repository: $REPO"
  echo; echo "== Variables =="; gh variable list --repo "$REPO" || warn "none / no access"
  echo; echo "== Secrets (names only; values are never readable) =="; gh secret list --repo "$REPO" || warn "none / no access"
}

check_gaps() {
  require_gh
  local vars secrets missing=0
  vars=$(existing_variables); secrets=$(existing_secrets)
  for v in "${REQUIRED_VARIABLES[@]}"; do
    grep -qx "$v" <<<"$vars" || { warn "MISSING variable: $v"; missing=1; }
  done
  for s in "${REQUIRED_SECRETS[@]}"; do
    grep -qx "$s" <<<"$secrets" || { warn "MISSING secret: $s"; missing=1; }
  done
  [ "$missing" -eq 0 ] && ok "All required variables and secrets are configured."
  return "$missing"
}

apply_config() {
  require_gh
  local vars secrets
  vars=$(existing_variables); secrets=$(existing_secrets)

  info "Repository: $REPO"

  # ---- Non-sensitive variables ----
  for v in "${REQUIRED_VARIABLES[@]}"; do
    if grep -qx "$v" <<<"$vars"; then
      ok "Variable already set: $v"
    else
      read -rp "Set value for variable ${v} (non-sensitive): " value
      [ -z "$value" ] && { warn "Skipped $v"; continue; }
      gh variable set "$v" --repo "$REPO" --body "$value"
      ok "Variable set: $v"
    fi
  done

  # ---- Secrets: delegate to gh's secure editor/stdin path ----
  for s in "${REQUIRED_SECRETS[@]}"; do
    if grep -qx "$s" <<<"$secrets"; then
      ok "Secret already set: $s"
    else
      warn "Secret missing: $s"
      read -rp "  Configure now? [y/N]: " confirm
      if [[ "$confirm" =~ ^[Yy]$ ]]; then
        case "$s" in
          SSH_PRIVATE_KEY)
            read -rp "  Path to private key file: " keyfile
            [ -f "$keyfile" ] || { err "  File not found: $keyfile"; continue; }
            gh secret set "$s" --repo "$REPO" < "$keyfile"
            ;;
          *)
            # No --body on the command line: gh opens a secure prompt.
            gh secret set "$s" --repo "$REPO"
            ;;
        esac
        ok "Secret set: $s"
      else
        info "  Skipped. Add later with: gh secret set $s --repo $REPO"
      fi
    fi
  done

  echo
  info "Final state:"
  check_gaps || warn "Some items still missing — deploy/build jobs referencing them will fail until configured."
}

case "${1:-apply}" in
  --list|list)   list_current ;;
  --check|check) check_gaps ;;
  --help|-h|help)
    sed -n '2,20p' "$0" ;;
  apply|"")      apply_config ;;
  *) err "Unknown option: $1"; exit 1 ;;
esac
