#!/usr/bin/env bash
# jev-detect.sh — Shell wrapper for jev-dynamic-detect
# Usage: jev-detect.sh "task text"

set -euo pipefail

TASK="${*:-}"
if [[ -z "$TASK" ]]; then
    echo "Usage: $0 \"task text\"" >&2
    exit 1
fi

# Resolve script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DETECT_SCRIPT="$SCRIPT_DIR/detect_optimized.py"

if [[ ! -f "$DETECT_SCRIPT" ]]; then
    echo "Error: detect_optimized.py not found at $DETECT_SCRIPT" >&2
    exit 1
fi

python3 "$DETECT_SCRIPT" "$TASK"