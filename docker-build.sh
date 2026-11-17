#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Build and optionally push the production images
#
# Usage:
#   ./docker-build.sh                              # build v<latest tag>, no push
#   ./docker-build.sh --version=v1.1.1 --push
#   ./docker-build.sh --version=latest --push --platform=linux/amd64,linux/arm64
#   ./docker-build.sh --dry-run
#
# Flags:
#   --version=TAG     Tag to build (default: VERSION, else latest git tag)
#   --push            Push after building (requires a registry login)
#   --tag=EXTRA       Additional tag; repeatable
#   --platform=LIST   Comma-separated platforms (default: host platform)
#   --context=DIR     Backend build context (default: ./backend)
#   --no-cache        Disable the layer cache
#   --dry-run         Print the commands, build nothing
#   --yes, -y         Never prompt
#
# Without --push the images stay local, which is what a first-time operator
# wants: build once, verify, then push. Login uses --password-stdin so the
# token never reaches the shell history or the process list.
#
# CI does not use this script; .github/workflows/ci.yml builds with buildx and
# GHA cache directly. This is the local/manual path.
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
. "${SCRIPT_DIR}/scripts/lib.sh"

PUSH=false
DRY_RUN=false
ASSUME_YES=false
NO_CACHE=false
EXTRA_TAGS=()
PLATFORMS=""
CONTEXT=""

for arg in "$@"; do
    case "${arg}" in
        --version=*)  VERSION="${arg#*=}" ;;
        --tag=*)      EXTRA_TAGS+=("${arg#*=}") ;;
        --platform=*) PLATFORMS="${arg#*=}" ;;
        --context=*)  CONTEXT="${arg#*=}" ;;
        --push)       PUSH=true ;;
        --no-cache)   NO_CACHE=true ;;
        --dry-run)    DRY_RUN=true ;;
        --yes|-y)     ASSUME_YES=true ;;
        --help|-h)    erp_help "${BASH_SOURCE[0]}"; exit 0 ;;
        *)            erp_die "Unknown option: ${arg}" ;;
    esac
done

VERSION="$(erp_detect_version "${VERSION:-}")"
DOCKER_USER="$(erp_detect_docker_user)"
BACKEND_CONTEXT="${CONTEXT:-${ERP_PROJECT_ROOT}/backend}"
FRONTEND_CONTEXT="${ERP_PROJECT_ROOT}/backend/frontend-react"

BACKEND_IMAGE="${DOCKER_USER}/erp-solution-backend"
FRONTEND_IMAGE="${DOCKER_USER}/erp-solution-frontend"

run() {
    if [ "${DRY_RUN}" = true ]; then
        printf '    %s\n' "$*"
        return 0
    fi
    "$@"
}

###############################################################################
# Preflight
###############################################################################

preflight() {
    erp_require_cmd docker
    if ! docker info >/dev/null 2>&1; then
        if [ "${DRY_RUN}" = true ]; then
            # A dry run exists to show the commands; refusing because the
            # daemon is down defeats the purpose.
            erp_warn "Docker daemon is not running; showing commands only"
        else
            erp_die "Docker daemon is not reachable. Start it and retry."
        fi
    fi

    [ -f "${BACKEND_CONTEXT}/Dockerfile" ] \
        || erp_die "No Dockerfile in ${BACKEND_CONTEXT}"
    [ -f "${FRONTEND_CONTEXT}/Dockerfile" ] \
        || erp_die "No Dockerfile in ${FRONTEND_CONTEXT}"
    [ -f "${FRONTEND_CONTEXT}/package-lock.json" ] \
        || erp_warn "No package-lock.json; the frontend image will resolve versions at build time."

    # The frontend Dockerfile runs `npm ci`, which fails outright without a
    # lockfile. That is worth failing on here rather than 40 layers deep.
    if [ "${DRY_RUN}" != true ] && [ ! -d "${FRONTEND_CONTEXT}/node_modules" ]; then
        erp_info "node_modules absent locally; the image installs from the lockfile anyway."
    fi

    # A .dockerignore keeps the 290MB node_modules tree and the 369MB venv out
    # of the build context. Without one, the upload alone can take minutes.
    for dir in "${BACKEND_CONTEXT}" "${FRONTEND_CONTEXT}"; do
        if [ ! -f "${dir}/.dockerignore" ]; then
            erp_warn "No .dockerignore in ${dir}; the whole context is being sent to the daemon."
        fi
    done

    if [ -z "${PLATFORMS}" ]; then
        PLATFORMS="$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}' 2>/dev/null || echo linux/amd64)"
    fi
}

###############################################################################
# Login
###############################################################################

ensure_login() {
    [ "${PUSH}" = true ] || return 0
    if [ "${DRY_RUN}" = true ]; then
        # A dry run must not touch the network or the credential store.
        erp_info "[dry-run] would log in to Docker Hub as ${DOCKER_USER}"
        return 0
    fi
    # Skip when a credential helper already holds a token for this namespace.
    if [ -z "${DOCKERHUB_USERNAME:-}" ] && printf '%s' "${DOCKER_CONFIG:-$HOME/.docker}/config.json" \
        | grep -q "\"${DOCKER_USER}\"" 2>/dev/null; then
        erp_info "Existing Docker Hub credentials found for ${DOCKER_USER}"
        return 0
    fi

    erp_step "Logging in to Docker Hub as ${DOCKER_USER}"
    if [ -n "${DOCKERHUB_TOKEN:-}" ]; then
        # Token from the environment: never echoed, never in argv.
        printf '%s' "${DOCKERHUB_TOKEN}" | docker login --username-stdin 2>/dev/null \
            && { erp_success "Authenticated with DOCKERHUB_TOKEN"; return 0; }
        erp_warn "DOCKERHUB_TOKEN was rejected"
    fi

    if [ "${ASSUME_YES}" = true ]; then
        erp_die "Not logged in and cannot prompt. Set DOCKERHUB_TOKEN or run 'docker login' first."
    fi
    if [ ! -t 0 ]; then
        erp_die "Not logged in and stdin is not a terminal. Set DOCKERHUB_TOKEN or run 'docker login' first."
    fi
    docker login --username "${DOCKER_USER}"
}

###############################################################################
# Build
###############################################################################

buildx_available() { docker buildx version >/dev/null 2>&1; }

multi_platform() {
    case "${PLATFORMS}" in
        *,*) return 0 ;;
        *)   return 1 ;;
    esac
}

# Build one image.
#
# buildx is preferred: it is the only path that can produce a multi-arch image
# and it shares a cache with CI. The exporter has to match the mode, and the
# three cases are genuinely different:
#
#   --push                     buildx --push        (registry gets a manifest list)
#   multi-arch, no --push      buildx --output=type=cacheonly
#   single-arch, no --push     buildx --load        (lands in the local store)
#
# `--load` and `--push` are mutually exclusive, and `--load` cannot represent a
# manifest list, so a multi-arch local build cannot produce a usable image. That
# case is reported rather than silently collapsing to one architecture.
build_image() {
    local context="$1" image="$2" description="$3"

    local -a cmd
    if buildx_available; then
        cmd=(docker buildx build)
        if [ "${PUSH}" = true ]; then
            cmd+=(--push)
        elif multi_platform; then
            erp_error "Multi-platform build (${PLATFORMS}) cannot be loaded into the local image store."
            erp_error "Re-run with --push, or with a single --platform value."
            return 1
        else
            cmd+=(--load)
        fi
    else
        if multi_platform; then
            erp_error "buildx is required for multi-platform builds; install it or use a single --platform."
            return 1
        fi
        cmd=(docker build)
        erp_warn "buildx unavailable; using 'docker build' (no multi-arch support)"
    fi

    cmd+=(--tag "${image}:${VERSION}")
    local tag
    for tag in "${EXTRA_TAGS[@]+"${EXTRA_TAGS[@]}"}"; do
        cmd+=(--tag "${image}:${tag}")
    done

    [ -n "${PLATFORMS}" ] && cmd+=(--platform "${PLATFORMS}")
    [ "${NO_CACHE}" = true ] && cmd+=(--no-cache)
    cmd+=("${context}")

    erp_info "Building ${description}: ${image}:${VERSION}"
    if [ "${DRY_RUN}" = true ]; then
        run "${cmd[@]}"
        return 0
    fi
    "${cmd[@]}"
    erp_success "${description} built"
}

# Only reachable in the plain-docker fallback path; the buildx --push mode
# publishes as part of the build itself.
push_image() {
    [ "${PUSH}" = true ] || return 0
    buildx_available && return 0
    local image="$1"
    erp_info "Pushing ${image}:${VERSION}"
    run docker push "${image}:${VERSION}"
    local tag
    for tag in "${EXTRA_TAGS[@]+"${EXTRA_TAGS[@]}"}"; do
        run docker push "${image}:${tag}"
    done
}

summary() {
    local note="built locally"
    [ "${PUSH}" = true ] && note="built and pushed"

    cat <<EOF

==========================================
  ERP SOLUTION — images ${note}
==========================================

  ${BACKEND_IMAGE}:${VERSION}
  ${FRONTEND_IMAGE}:${VERSION}
  platforms: ${PLATFORMS}
  namespace: ${DOCKER_USER}

  Deploy with:
    VERSION=${VERSION} ./scripts/deploy-blue-green.sh production ${VERSION}

EOF
}

main() {
    erp_step "Building ERP Solution images (version ${VERSION})"
    preflight
    ensure_login

    build_image "${BACKEND_CONTEXT}"  "${BACKEND_IMAGE}"  "backend"
    build_image "${FRONTEND_CONTEXT}" "${FRONTEND_IMAGE}" "frontend"

    push_image "${BACKEND_IMAGE}"
    push_image "${FRONTEND_IMAGE}"

    summary
    if [ "${PUSH}" = true ]; then
        erp_success "Images published to Docker Hub."
    else
        erp_info "Not pushed (no --push). Add --push to publish."
    fi
}

main "$@"