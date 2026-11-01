#!/usr/bin/env python3
"""Compatibility shim for the Jev-Intercept skill.

The reusable implementation lives in ``backend/app/services/jev_intercept.py``
so the FastAPI app and this skill share one code path. Import this module with
the repository's backend interpreter (``backend/venv/bin/python``), because the
shared module imports Starlette.

    backend/venv/bin/python -c "import sys; sys.path.insert(0, '.opencode/skills/jev-intercept/scripts'); import interceptor; print(interceptor.events_file())"
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[4] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.jev_intercept import (  # noqa: E402,F401
    InterceptMiddleware,
    enabled,
    event_count,
    events_file,
    install_interceptor,
    install_sqlalchemy_interceptor,
    install_tracing,
    redact,
    repo_root,
    summarize_body,
    write_event,
)
