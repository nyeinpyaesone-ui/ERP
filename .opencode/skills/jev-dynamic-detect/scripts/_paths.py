"""Shared path resolution for the jev-dynamic-detect scripts.

Skill roots differ per host: OpenCode may install skills under
``$HOME/.opencode/skills`` or ``$HOME/.config/opencode/skills``, and project
skills live under ``<repo>/.opencode/skills``. Nothing here may hardcode an
absolute machine path.
"""

from __future__ import annotations

import os
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(os.getenv("JEV_ERP_REPO_ROOT", str(SKILL_ROOT.parents[2])))


def skill_roots() -> list[Path]:
    """Return candidate skill roots, most specific first."""
    roots: list[Path] = []
    override = os.getenv("JEV_SKILLS_ROOT")
    if override:
        roots.append(Path(override).expanduser())
    roots.append(REPO_ROOT / ".opencode" / "skills")
    # A checkout usually lives under its owner's home (e.g.
    # /home/admin/projects/ERP), so that home's skill root is a candidate too.
    if len(REPO_ROOT.parents) > 1:
        roots.append(REPO_ROOT.parents[1] / ".opencode" / "skills")
    roots.extend(
        [
            Path.home() / ".opencode" / "skills",
            Path.home() / ".config" / "opencode" / "skills",
        ]
    )
    return roots


def skill_script(skill: str, relative: str) -> Path | None:
    """Locate ``<skill>/<relative>`` under any known skill root.

    ``JEV_<SKILL>_SCRIPT`` (e.g. ``JEV_JEV_DEVOPS_SCRIPT``) wins when set.
    """
    env_key = "JEV_" + skill.replace("-", "_").upper() + "_SCRIPT"
    override = os.getenv(env_key)
    if override:
        candidate = Path(override).expanduser()
        return candidate if candidate.exists() else None
    for root in skill_roots():
        candidate = root / skill / relative
        if candidate.exists():
            return candidate
    return None
