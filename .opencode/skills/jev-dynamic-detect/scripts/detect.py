#!/usr/bin/env python3
"""Dynamic detect entrypoint for OpenCode agents.

Usage:
  python3 scripts/detect.py "task text"
  python3 scripts/detect.py --erp-context

Enriches the task with ERP context and routes it through the jev-devops
auto router. Simulation mode by default; upgrades to real Jev only when a key
is present and the user approves. Paths resolve through ``_paths`` so no
machine-specific absolute path is required.
"""

import json
import os
import subprocess
import sys

from _paths import REPO_ROOT, skill_script

JEV_DEVOPS_ROUTER = skill_script("jev-devops", "scripts/auto_router.py")
JEV_CLI = skill_script("jev", "scripts/jev.py")


def erp_context():
    ctx = {}
    try:
        ctx["last_commit"] = subprocess.check_output(
            ["git", "log", "-1", "--oneline"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        ctx["last_commit"] = None
    ctx["ci"] = os.getenv("JEV_CI_STATUS", "unknown")
    ctx["error_budget"] = "unknown"
    return ctx


def enrich(task):
    ctx = erp_context()
    return (
        f"{task}\n[ERP context last_commit={ctx.get('last_commit')} "
        f"ci={ctx.get('ci')}]"
    )


def route(task):
    if JEV_DEVOPS_ROUTER is None:
        return {
            "error": "jev-devops auto_router.py not found",
            "hint": "install the jev-devops skill or set JEV_JEV_DEVOPS_SCRIPT",
        }
    try:
        proc = subprocess.run(
            [sys.executable, str(JEV_DEVOPS_ROUTER), "--verbose", task],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"error": str(exc)}
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"error": proc.stdout, "stderr": proc.stderr}


def main():
    if len(sys.argv) < 2:
        print('Usage: detect.py "task text"', file=sys.stderr)
        sys.exit(1)

    task = enrich(" ".join(sys.argv[1:]))
    result = route(task)
    has_key = bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("TYPESAFE_API_KEY"))
    result["mode"] = (
        "agent_simulation" if not has_key else "agent_simulation_pending_approval"
    )
    result["jev_called"] = False
    result["needs_review"] = True
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
