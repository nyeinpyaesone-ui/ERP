#!/usr/bin/env bash
# Configure read-only Docker Hub access on a deployment host using a native
# Docker credential helper. The token is read silently and never written to a file.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/configure-host-registry.sh --docker-user NAMESPACE --image-tag sha-...|v...

Requires a configured Docker credential helper (credsStore or Docker Hub
credHelpers). The token must be a read-only Docker Hub access token.
USAGE
}
docker_user=""
image_tag=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --docker-user) docker_user="$2"; shift 2 ;;
    --image-tag) image_tag="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ "$docker_user" =~ ^[a-z0-9][a-z0-9_-]{0,127}$ ]] || { echo "Invalid Docker Hub namespace" >&2; exit 2; }
[[ "$image_tag" =~ ^(sha-[[:xdigit:]]{7,40}|v[0-9A-Za-z][0-9A-Za-z._-]{0,127})$ ]] || { echo "Use an immutable sha-* or v* image tag; latest is rejected" >&2; exit 2; }
command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required to inspect Docker credential configuration" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker daemon is not reachable" >&2; exit 1; }

docker_config="${DOCKER_CONFIG:-$HOME/.docker}/config.json"
[ -f "$docker_config" ] || { echo "No Docker config found at $docker_config; configure a credential helper first" >&2; exit 1; }
helper="$(python3 - "$docker_config" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as f:
    config = json.load(f)
helpers = config.get("credHelpers", {})
print(helpers.get("https://index.docker.io/v1/") or helpers.get("docker.io") or config.get("credsStore") or "")
PY
)"
[ -n "$helper" ] || { echo "No Docker credential helper is configured; refusing to store a base64 token in config.json" >&2; exit 1; }
command -v "docker-credential-$helper" >/dev/null 2>&1 || { echo "Credential helper docker-credential-$helper is not installed" >&2; exit 1; }

[ -t 0 ] || { echo "Run interactively so the read-only token can be entered without echo" >&2; exit 1; }
read -r -s -p "Docker Hub read-only token for $docker_user: " token
printf '\n'
[ -n "$token" ] || { unset token; echo "Token cannot be empty" >&2; exit 1; }
if ! printf '%s' "$token" | docker login --username "$docker_user" --password-stdin; then
  unset token
  echo "Docker Hub login failed" >&2
  exit 1
fi
unset token

docker manifest inspect "$docker_user/erp-solution-backend:$image_tag" >/dev/null
docker manifest inspect "$docker_user/erp-solution-frontend:$image_tag" >/dev/null
echo "Read-only registry access verified for both ERP images at tag $image_tag."
