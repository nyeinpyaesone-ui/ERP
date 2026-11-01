---
name: jev-dynamic-detect
description: Auto-dynamic detection mode that routes free-text tasks to Jev-type DevOps judgments using the jev-devops router. Simulates when no key is present; upgrades to real Jev when OPENROUTER_API_KEY or TYPESAFE_API_KEY is configured and approved.
---

# jev-dynamic-detect

Combines Jev AI typed-decision technology with OpenCode agents for advanced auto-dynamic detect mode.

## Purpose

* Detect the appropriate Jev DevOps scenario from natural language task text.
* Enrich the detection with ERP context: CI status, recent commits, test receipts, error budget.
* Return a Jev-compatible envelope: `mode`, `jev_called`, `probability`, `confidence`, `needs_review`.
* Simulation by default; real Jev only after explicit user approval and key presence.

## Workflow

1. Pre-process task with ERP context.
2. Run jev-devops auto_router.
3. If router picks a skill and a Jev key is present → build request JSON → `jev-decide decide <request.json>`.
4. If no key → simulate decisions with the same template questions.
5. Return reviewable table and never auto-execute actions.

## Integration

* Located at `.opencode/skills/jev-dynamic-detect`.
* Entrypoints: `scripts/detect.py "task"` (minimal) and
  `scripts/detect_optimized.py "task"` (config-driven, cached ERP context,
  audit trail).
* Paths resolve through `scripts/_paths.py`: no machine-specific absolute
  paths. `JEV_ERP_REPO_ROOT` overrides the repo root, `JEV_SKILLS_ROOT`
  overrides where sibling skills are searched, and
  `JEV_JEV_DEVOPS_SCRIPT` points directly at `auto_router.py`.
* `config.json` → `erp_context.git.repo_path` is repo-relative (`.`).
* Called via `@jev-dynamic-detect` in OpenCode.
* Permissions: shell for `scripts/auto_router.py` and `jev-decide` only when
  approved.

## Quick check

```bash
python3 .opencode/skills/jev-dynamic-detect/scripts/detect.py "review this CI change"
# → mode=agent_simulation, jev_called=false, needs_review=true
```

## Safety

* No keys printed.
* No paid calls without explicit approval.
* `needs_review: true` on all decisions.
* Advisory only.
