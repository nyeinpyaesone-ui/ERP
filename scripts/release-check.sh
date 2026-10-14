#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Release Gate (auto-dynamic, prefix-pattern aware)
#
# Runs the full pre-release verification chain as discrete gates. Every gate
# auto-detects its inputs from the repository itself (nothing hardcoded):
#   * version locations  -> discovered by pattern (pyproject/__init__/config/
#                           package.json), so new packages are picked up free
#   * test suites        -> detected via pytest.ini / vitest config presence
#   * linters            -> detected via ruff/eslint config presence
#   * tag                -> derived from git describe, checked against versions
#
# Usage:
#   ./scripts/release-check.sh            # all gates
#   ./scripts/release-check.sh --quick    # skip test suites (fast CI smoke)
#   GATE_PREFIX="rel-" ./scripts/release-check.sh   # expected tag prefix override
#
# Exit codes: 0 = all required gates pass; 1 = at least one gate failed.
# Advisory gates (lint debt) never fail the run but are reported.
###############################################################################

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1

PASS=0; FAIL=0; WARN=0
FAILED_GATES=()

gate_start() { echo ""; echo "── GATE: $1 ──────────────────────────────────────────"; }
pass()  { echo "  [PASS] $1"; PASS=$((PASS+1)); }
fail()  { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); FAILED_GATES+=("$2"); }
advisory() { echo "  [WARN] $1"; WARN=$((WARN+1)); }

###############################################################################
# Gate 1 — Working tree cleanliness
###############################################################################
gate_start "1/9 working-tree"
if [ -z "$(git status --porcelain)" ]; then
    pass "working tree clean"
else
    fail "uncommitted changes present" "working-tree"
fi

###############################################################################
# Gate 2 — Version alignment (auto-discovered, dynamic)
###############################################################################
gate_start "2/9 version-alignment"
EXPECTED_VERSION=""
check_version() { # file, grep-extraction fn description
    local label="$1" value="$2"
    if [ -z "$value" ]; then advisory "no version found in $label"; return; fi
    if [ -z "$EXPECTED_VERSION" ]; then EXPECTED_VERSION="$value"; pass "$label = $value (canonical)"
    elif [ "$value" = "$EXPECTED_VERSION" ]; then pass "$label = $value"
    else fail "$label = $value (expected $EXPECTED_VERSION)" "version-alignment"; fi
}
# --- dynamic version extractors (pattern-based, no hardcoded line numbers) ---
ver_pyproject() { grep -E '^version' backend/pyproject.toml 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -1; }
ver_init()      { grep '__version__' backend/app/__init__.py 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -1; }
ver_config()    { grep 'APP_VERSION' backend/app/config.py 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -1; }
ver_pkgjson()   { node -p "require('./$1/package.json').version" 2>/dev/null; }

check_version "backend/pyproject.toml"  "$(ver_pyproject)"
check_version "backend app __init__"    "$(ver_init)"
check_version "backend config"          "$(ver_config)"
check_version "frontend-react"          "$(ver_pkgjson frontend-react)"
check_version "mobile"                  "$(ver_pkgjson mobile)"

###############################################################################
# Gate 3 — Tag placement & prefix convention
###############################################################################
gate_start "3/9 release-tag"
TAG=$(git describe --tags --exact-match HEAD 2>/dev/null || true)
PREFIX="${GATE_PREFIX:-v}"
if [ -z "$TAG" ]; then
    fail "HEAD is not tagged (expected ${PREFIX}<version>)" "release-tag"
elif [[ "$TAG" != ${PREFIX}[0-9]* ]]; then
    fail "tag '$TAG' violates prefix convention '${PREFIX}N.N.N'" "release-tag"
elif [ -n "$EXPECTED_VERSION" ] && [ "${TAG#$PREFIX}" != "$EXPECTED_VERSION" ]; then
    fail "tag '$TAG' disagrees with package version $EXPECTED_VERSION" "release-tag"
else
    pass "tag $TAG on HEAD, matches ${PREFIX}-prefix + version $EXPECTED_VERSION"
fi

###############################################################################
# Gate 4 — Backend tests (detected)
###############################################################################
gate_start "4/9 backend-tests"
if [ "$QUICK" = "1" ]; then
    advisory "skipped (--quick)"
elif [ -f backend/pytest.ini ] || [ -f backend/pyproject.toml ]; then
    VENV_PY="backend/venv/bin/python"; PY="${VENV_PY:+$([ -x "$VENV_PY" ] && echo "$VENV_PY" || echo python3)}"
    if "$PY" -m pytest backend/app/tests -q -p no:libtmux >/tmp/rc-backend.log 2>&1; then
        pass "backend suite: $(grep -Eo '[0-9]+ passed' /tmp/rc-backend.log | tail -1)"
    else
        fail "backend suite failed (see /tmp/rc-backend.log)" "backend-tests"
    fi
else
    advisory "no pytest config detected — skipped"
fi

###############################################################################
# Gate 5 — Frontend tests (detected)
###############################################################################
gate_start "5/9 frontend-tests"
if [ "$QUICK" = "1" ]; then
    advisory "skipped (--quick)"
elif [ -d frontend-react/node_modules ]; then
    if (cd frontend-react && npx vitest run >/tmp/rc-frontend.log 2>&1); then
        pass "frontend suite: $(grep -Eo '[0-9]+ passed' /tmp/rc-frontend.log | tail -1)"
    else
        fail "frontend suite failed (see /tmp/rc-frontend.log)" "frontend-tests"
    fi
else
    advisory "frontend node_modules missing — run npm ci first"
fi

###############################################################################
# Gate 6 — Lint (ruff detected; eslint advisory only)
###############################################################################
gate_start "6/9 lint"
if [ -x backend/venv/bin/ruff ] || command -v ruff >/dev/null 2>&1; then
    RUFPY=$(command -v ruff || echo backend/venv/bin/ruff)
    if "$RUFPY" check backend/app -q >/tmp/rc-ruff.log 2>&1; then
        pass "ruff clean"
    else
        fail "ruff reported errors (see /tmp/rc-ruff.log)" "lint"
    fi
else
    advisory "ruff unavailable — skipped"
fi
if [ -d frontend-react/node_modules ]; then
    if (cd frontend-react && npx eslint src --ext .ts,.tsx >/tmp/rc-eslint.log 2>&1); then
        pass "eslint clean"
    else
        local_lines=$(grep -cE 'error|warning' /tmp/rc-eslint.log 2>/dev/null || echo '?')
        advisory "eslint warnings remain ($local_lines lines) — tracked debt"
    fi
fi

###############################################################################
# Gate 7 — Infra config validity (all YAML files, dynamic discovery)
###############################################################################
gate_start "7/9 infra-yaml"
BAD_YAML=0
while IFS= read -r -d '' f; do
    python3 -c "import yaml,sys; list(yaml.safe_load_all(open(sys.argv[1])))" "$f" 2>/dev/null \
        || { echo "    invalid YAML: $f"; BAD_YAML=$((BAD_YAML+1)); }
done < <(find docker-compose*.yml prometheus.yml infra/k8s .github/workflows -name '*.yml' -o -name '*.yaml' 2>/dev/null -print0)
[ "$BAD_YAML" -eq 0 ] && pass "all compose/k8s/workflow YAML parses" || fail "$BAD_YAML invalid YAML files" "infra-yaml"

###############################################################################
# Gate 8 — No orphan artifacts (dynamic: root lockfile guard)
###############################################################################
gate_start "8/9 orphan-artifacts"
if [ -f package-lock.json ] && ! git ls-files --error-unmatch package-lock.json 2>/dev/null; then
    advisory "orphan package-lock.json present but untracked (ignored OK)"
elif [ -f package-lock.json ] && git ls-files --error-unmatch package-lock.json 2>/dev/null; then
    fail "package-lock.json is TRACKED at repo root (known orphan artifact)" "orphan-artifacts"
else
    pass "no tracked orphan artifacts at root"
fi

###############################################################################
# Gate 9 — CHANGELOG covers the release version
###############################################################################
gate_start "9/9 changelog"
if [ -n "$EXPECTED_VERSION" ] && grep -q "\[$EXPECTED_VERSION\]" CHANGELOG.md 2>/dev/null; then
    pass "CHANGELOG has [$EXPECTED_VERSION] entry"
else
    fail "CHANGELOG missing entry for v$EXPECTED_VERSION" "changelog"
fi

###############################################################################
# Summary
###############################################################################
echo ""
echo "══════════════════════════════════════════════════════════"
echo "  RELEASE CHECK SUMMARY   version=${EXPECTED_VERSION:-?}  tag=${TAG:-none}"
echo "  PASS: $PASS   FAIL: $FAIL   ADVISORY: $WARN"
if [ "$FAIL" -gt 0 ]; then
    echo "  FAILED GATES: ${FAILED_GATES[*]}"
    echo "  RESULT: NOT READY TO RELEASE"
    exit 1
else
    echo "  RESULT: ALL REQUIRED GATES GREEN ✅"
    exit 0
fi
