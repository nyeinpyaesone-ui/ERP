#!/usr/bin/env python3
"""Optimized dynamic detect for technical standards staff.

Features:
- Config-driven router thresholds, cache TTL, ERP context sources
- LRU cache for git/CI context
- Structured audit trail
- Simulation by default, real Jev gated by approval

Paths resolve through ``_paths.skill_script`` so the skill works from any
checkout, skill root or user account (override with ``JEV_SKILLS_ROOT`` or
``JEV_JEV_DEVOPS_SCRIPT``).
"""

import json
import os
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path

from _paths import REPO_ROOT, SKILL_ROOT, skill_script

CONFIG_PATH = SKILL_ROOT / "config.json"
JEV_DEVOPS_ROUTER = skill_script("jev-devops", "scripts/auto_router.py")


@lru_cache(maxsize=32)
def load_config():
    with open(CONFIG_PATH) as handle:
        return json.load(handle)


def repo_path() -> Path:
    """Resolve ``erp_context.git.repo_path`` relative to the repo root."""
    configured = Path(load_config()["erp_context"]["git"].get("repo_path", "."))
    return configured if configured.is_absolute() else REPO_ROOT / configured


@lru_cache(maxsize=8)
def git_last_commit():
    repo = repo_path()
    return subprocess.check_output(
        ["git", "log", "-1", "--oneline"], cwd=repo, text=True
    ).strip()


@lru_cache(maxsize=8)
def git_dirty():
    repo = repo_path()
    out = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=repo, text=True
    ).strip()
    return bool(out)


def erp_context():
    cfg = load_config()
    ctx = {}
    sources = cfg["erp_context"]["sources"]
    if "git_last_commit" in sources:
        ctx["last_commit"] = git_last_commit()
    if "git_dirty" in sources:
        ctx["dirty"] = git_dirty()
    if "ci_status" in sources:
        ctx["ci"] = os.getenv("JEV_CI_STATUS", "unknown")
    if "test_coverage" in sources:
        ctx["coverage"] = os.getenv("JEV_TEST_COVERAGE", "unknown")
    if "error_budget" in sources:
        ctx["error_budget"] = "unknown"
    return ctx


def enrich_task(task):
    ctx = erp_context()
    ctx_str = "; ".join(f"{k}={v}" for k, v in ctx.items())
    return f"{task}\n[ERP context {ctx_str}]"


def route(task):
    """Run the jev-devops auto router and return its JSON envelope."""
    if JEV_DEVOPS_ROUTER is None:
        return {
            "error": "jev-devops auto_router.py not found",
            "hint": "install the jev-devops skill or set JEV_JEV_DEVOPS_SCRIPT",
        }

    cfg = load_config()
    args = [sys.executable, str(JEV_DEVOPS_ROUTER)]
    if cfg["router"]["verbose"]:
        args.append("--verbose")
    args.append(task)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"error": str(exc)}

    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"error": proc.stdout, "stderr": proc.stderr}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": 'Usage: detect_optimized.py "task text"'}))
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    start = time.time()
    result = route(enrich_task(task))
    result["mode"] = "agent_simulation"
    result["jev_called"] = False
    result["needs_review"] = True
    result["audit"] = {
        "timestamp": int(time.time()),
        "duration_ms": int((time.time() - start) * 1000),
        "config": load_config()["name"],
        "standards": load_config()["standards"]["compliance"],
    }
    if load_config()["output"]["pretty_print"]:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
