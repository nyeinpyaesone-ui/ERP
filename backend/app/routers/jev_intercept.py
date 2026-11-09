"""Collector endpoints for the Jev-Intercept skill.

Mounted by ``app.main.ROUTER_MOUNTS`` at ``/api/v1/jev``; this module must not
carry a prefix of its own or the version segment would be applied twice.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.services.jev_intercept import enabled, event_count, events_file, write_event
from app.services.permissions import require_permission

router = APIRouter(tags=["Jev-Intercept"])


def require_enabled() -> None:
    """Keep the collector inert unless ``JEV_INTERCEPT=1`` is set.

    Without this the endpoint would let any authenticated user append
    arbitrary lines to the events file in an environment where nobody asked
    for interception (log injection / disk fill).
    """
    if not enabled():
        raise HTTPException(status_code=404, detail="Jev interception is disabled")


@router.post("/intercept", dependencies=[Depends(require_enabled)])
async def collect_intercept(
    request: Request,
    current_user=Depends(require_permission("jev_intercept", "create")),
) -> JSONResponse:
    """Persist one frontend/agent interception event."""
    try:
        body: Any = await request.json()
    except Exception:
        return JSONResponse(
            {"ok": False, "error": "invalid JSON body"}, status_code=400
        )

    if not isinstance(body, dict):
        body = {"payload": body}
    body["source"] = "frontend"
    body.setdefault("request_id", request.headers.get("x-request-id", "unknown"))
    try:
        write_event(body)
    except OSError as exc:  # pragma: no cover - disk/permission failures
        return JSONResponse(
            {"ok": False, "error": f"event not persisted: {exc}"}, status_code=503
        )
    return JSONResponse({"ok": True})


@router.get("/intercept/status")
async def intercept_status(
    current_user=Depends(require_permission("jev_intercept", "read")),
) -> dict[str, Any]:
    """Return whether interception is enabled and where events are stored."""
    path = events_file()
    return {
        "enabled": enabled(),
        "events_file": str(path),
        "events_count": event_count(),
    }
