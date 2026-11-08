#!/usr/bin/env bash
# Create a fresh, environment-isolated Compose runtime file with generated secrets.
# This script never prints secret values and never overwrites an existing file.
set -euo pipefail
umask 077

usage() {
  cat <<'USAGE'
Usage:
  scripts/configure-environment.sh --environment staging|production --domain FQDN --docker-user NAMESPACE [options]

Options:
  --environment NAME   Target environment (required)
  --domain FQDN        Base domain, e.g. staging.example.com (required)
  --docker-user NAME   Docker Hub namespace (required)
  --version TAG        Initial image tag (default: latest; use an immutable tag for deploys)
  --dir PATH           Required absolute install directory outside the repository
  --help               Show this help

Creates .env.staging or .env.production with distinct random DB, Redis, and
application secrets. Run once on each dedicated host. Existing files are never
overwritten. Keep the file outside version control and mode 0600.
USAGE
}

environment=""
domain=""
docker_user=""
version="latest"
target_dir=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --environment) [ "$#" -ge 2 ] || { echo "Missing value for --environment" >&2; exit 2; }; environment="$2"; shift 2 ;;
    --domain) [ "$#" -ge 2 ] || { echo "Missing value for --domain" >&2; exit 2; }; domain="$2"; shift 2 ;;
    --docker-user) [ "$#" -ge 2 ] || { echo "Missing value for --docker-user" >&2; exit 2; }; docker_user="$2"; shift 2 ;;
    --version) [ "$#" -ge 2 ] || { echo "Missing value for --version" >&2; exit 2; }; version="$2"; shift 2 ;;
    --dir) [ "$#" -ge 2 ] || { echo "Missing value for --dir" >&2; exit 2; }; target_dir="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$environment" in
  staging|production) ;;
  *) echo "--environment must be staging or production" >&2; exit 2 ;;
esac

if [[ ! "$domain" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]]; then
  echo "--domain must be a lowercase FQDN without scheme, path, or port" >&2
  exit 2
fi
if [[ ! "$docker_user" =~ ^[a-z0-9][a-z0-9_-]{0,127}$ ]]; then
  echo "--docker-user must be a valid lowercase Docker Hub namespace" >&2
  exit 2
fi
if [[ ! "$version" =~ ^(latest|sha-[[:xdigit:]]{7,40}|v[0-9A-Za-z][0-9A-Za-z._-]{0,127})$ ]]; then
  echo "--version must be latest, sha-* or v*; use immutable tags for deploys" >&2
  exit 2
fi
command -v openssl >/dev/null 2>&1 || { echo "openssl is required" >&2; exit 1; }

[ -n "$target_dir" ] || { echo "--dir is required; choose the environment's protected install directory" >&2; exit 2; }
case "$target_dir" in
  /*) ;;
  *) echo "--dir must be an absolute path" >&2; exit 2 ;;
esac

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$target_dir"
target_dir="$(cd "$target_dir" && pwd)"
case "$target_dir" in
  "$repo_root"|"$repo_root"/*)
    echo "Refusing to create runtime credentials inside the Git working tree." >&2
    exit 2
    ;;
esac
env_file="$target_dir/.env.$environment"
if [ -e "$env_file" ] || [ -L "$env_file" ]; then
  echo "Refusing to overwrite existing $env_file" >&2
  exit 1
fi

tmp_file="$(mktemp "$target_dir/.env.$environment.tmp.XXXXXX")"
cleanup() { rm -f -- "$tmp_file"; }
trap cleanup EXIT HUP INT TERM

db_password="$(openssl rand -hex 32)"
redis_password="$(openssl rand -hex 32)"
secret_key="$(openssl rand -hex 32)"
generated_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

cat > "$tmp_file" <<EOF
# ERP SOLUTION runtime configuration
# Generated: $generated_at
# Environment target: $environment (backend ENVIRONMENT remains prod)
# Never commit this file. File permissions are set to 0600.

# Docker Compose infrastructure values
DB_USER=erp
DB_PASSWORD=$db_password
DB_NAME=erp_solution
REDIS_PASSWORD=$redis_password
DOCKER_USER=$docker_user
VERSION=$version

# Backend runtime (values match backend/app/config.py)
DEBUG=false
ENVIRONMENT=prod
SECRET_KEY=$secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=https://app.$domain
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1
UPLOAD_DIR=/app/uploads
MAX_UPLOAD_SIZE=52428800
WS_HEARTBEAT_INTERVAL=30

# Optional integrations. Keep blank until valid provider credentials exist.
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@$domain
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PUBLISHABLE_KEY=
EOF

chmod 600 "$tmp_file"
if ! ln -- "$tmp_file" "$env_file"; then
  echo "Refusing to overwrite existing $env_file" >&2
  exit 1
fi
rm -f -- "$tmp_file"
trap - EXIT HUP INT TERM

printf 'Created %s (mode 0600). Secret values were not printed.\n' "$env_file"
printf 'Next: verify ownership, provision read-only registry credentials, then run the install/deploy preflight.\n'
