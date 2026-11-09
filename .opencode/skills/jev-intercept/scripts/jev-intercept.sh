#!/usr/bin/env bash
# jev-intercept.sh — Shell wrapper for jev-intercept
# Usage: jev-intercept.sh {start|trace|judge|status|help}

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="/home/admin/projects/ERP/backend"

usage() {
    cat <<EOF
Usage: $0 {start|trace|judge|status|help}

Commands:
  start    Start backend with JEV_INTERCEPT=1
  trace    Start backend with JEV_INTERCEPT=1 and JEV_INTERCEPT_TRACE=1
  judge    Run jev_judge.py on collected events
  status   Query collector status (requires running backend)
  help     Show this help
EOF
}

case "${1:-help}" in
    start)
        cd "$BACKEND_DIR"
        . venv/bin/activate
        JEV_INTERCEPT=1 exec uvicorn app.main:app --reload
        ;;
    trace)
        cd "$BACKEND_DIR"
        . venv/bin/activate
        JEV_INTERCEPT=1 JEV_INTERCEPT_TRACE=1 exec uvicorn app.main:app --reload
        ;;
    judge)
        cd "$BACKEND_DIR"
        . venv/bin/activate
        exec python "$SCRIPT_DIR/jev_judge.py"
        ;;
    status)
        curl -s http://localhost:8000/api/v1/jev/intercept/status | python3 -m json.tool
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        echo "Unknown command: $1" >&2
        usage
        exit 1
        ;;
esac