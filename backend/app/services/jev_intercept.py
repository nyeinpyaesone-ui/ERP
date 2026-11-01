"""Reusable runtime interception for the Jev-Intercept skill.

The interceptor is opt-in: nothing is installed unless ``JEV_INTERCEPT=1``.
Events are written as JSON Lines so they can be tailed, replayed, or fed to
the Jev judge script without a database.

Request bodies are captured lazily: the middleware only records what the
application itself reads, so it never buffers or replays uploads. Endpoints
that parse a body (the normal FastAPI case) are recorded; endpoints that
ignore the body record an empty ``request_body``.

Environment:
    JEV_INTERCEPT              ``1`` enables the middleware (default: off)
    JEV_INTERCEPT_TRACE        ``1`` additionally enables ``sys.settrace``
    JEV_INTERCEPT_MODULES      Comma-separated module prefixes to trace
    JEV_INTERCEPT_EVENTS_FILE  Override the JSONL output path
    JEV_INTERCEPT_MAX_BODY     Max request/response bytes retained (default 2000)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
import uuid
from collections.abc import Mapping
from contextvars import ContextVar
from pathlib import Path
from typing import Any

REDACT_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "key",
        "authorization",
        "ssn",
        "credit_card",
    }
)

logger = logging.getLogger(__name__)

_WRITE_LOCK = threading.Lock()
_REQUEST_ID: ContextVar[str] = ContextVar("jev_request_id", default="")
_SPAN_ID: ContextVar[int] = ContextVar("jev_span_id", default=0)


def repo_root() -> Path:
    """Locate the repository root for default event paths.

    Honours ``JEV_ERP_REPO_ROOT`` first, then walks up from this file looking
    for a ``.git`` or ``.opencode`` directory, and finally falls back to the
    current working directory (e.g. inside a container image where neither
    marker is shipped).
    """
    override = os.getenv("JEV_ERP_REPO_ROOT")
    if override:
        return Path(override).expanduser()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists() or (parent / ".opencode").exists():
            return parent
    return Path.cwd()


def events_file() -> Path:
    """Return the active JSONL event path, honouring the env override."""
    override = os.getenv("JEV_INTERCEPT_EVENTS_FILE")
    if override:
        return Path(override).expanduser()
    return repo_root() / ".opencode" / "intercept" / "events.jsonl"


def enabled() -> bool:
    """Return ``True`` when interception is switched on for this process."""
    return os.getenv("JEV_INTERCEPT") == "1"


def redact(value: Any) -> Any:
    """Recursively replace sensitive mapping keys with ``***``."""
    if isinstance(value, Mapping):
        return {
            key: "***" if str(key).lower() in REDACT_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


def write_event(event: Mapping[str, Any]) -> None:
    """Append one event to the JSONL stream, creating parent directories."""
    path = events_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": time.time(),
        "request_id": _REQUEST_ID.get(),
        "span_id": _SPAN_ID.get(),
        **event,
    }
    line = json.dumps(record, default=str)
    with _WRITE_LOCK, path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def event_count() -> int:
    """Return the number of recorded events (0 when the file is absent)."""
    path = events_file()
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _decode(chunk: bytes) -> str:
    return chunk.decode("utf-8", errors="replace")


_FORM_SECRET = re.compile(r"(?i)\b(" + "|".join(sorted(REDACT_KEYS)) + r")=([^&\s\"]+)")


def summarize_body(chunk: bytes) -> Any:
    """Return a redacted, JSON-friendly summary of a captured body.

    JSON bodies are parsed and redacted structurally; form-encoded or opaque
    bodies fall back to masking ``key=value`` pairs for sensitive keys.
    """
    text = _decode(chunk)
    if not text:
        return ""
    try:
        return redact(json.loads(text))
    except ValueError:
        return _FORM_SECRET.sub(r"\1=***", text)


def _safe_write(event: Mapping[str, Any]) -> None:
    """Write an event without ever breaking the request it describes."""
    try:
        write_event(event)
    except OSError as exc:  # pragma: no cover - disk/permission failures
        logger.warning("[jev-intercept] event write skipped: %s", exc)


class InterceptMiddleware:
    """Pure-ASGI middleware that records request/response summaries as JSONL.

    The middleware never buffers a request to replay it and never drains a
    response stream: it observes the ``http.request`` chunks the application
    reads and the ``http.response.body`` chunks it sends, keeping at most
    ``JEV_INTERCEPT_MAX_BODY`` bytes of each. Streaming endpoints therefore
    keep streaming, and large uploads are never held in memory.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        limit = int(os.getenv("JEV_INTERCEPT_MAX_BODY", "2000"))
        request_id = uuid.uuid4().hex[:12]
        token = _REQUEST_ID.set(request_id)
        start = time.perf_counter()
        request_body = bytearray()
        response_body = bytearray()
        response_status = 0

        async def receive_wrapper():
            message = await receive()
            if message.get("type") == "http.request" and len(request_body) < limit:
                remaining = limit - len(request_body)
                request_body.extend(message.get("body", b"")[:remaining])
            return message

        async def send_wrapper(message):
            nonlocal response_status
            if message.get("type") == "http.response.start":
                response_status = message.get("status", 0)
            elif (
                message.get("type") == "http.response.body"
                and len(response_body) < limit
            ):
                remaining = limit - len(response_body)
                response_body.extend(message.get("body", b"")[:remaining])
            await send(message)

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except Exception as exc:
            _safe_write(
                {
                    "type": "request_error",
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "error": str(exc),
                }
            )
            raise
        finally:
            _safe_write(
                {
                    "type": "http_request",
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "query_string": _decode(scope.get("query_string", b"")),
                    "request_body": summarize_body(bytes(request_body)),
                    "response_status": response_status,
                    "response_body": summarize_body(bytes(response_body)),
                    "duration_ms": (time.perf_counter() - start) * 1000,
                }
            )
            _REQUEST_ID.reset(token)


def _trace_depth(frame) -> int:
    depth = 0
    current = frame.f_back
    while current is not None:
        depth += 1
        current = current.f_back
    return depth


def install_tracing() -> None:
    """Enable opt-in ``sys.settrace`` instrumentation for configured modules."""
    if os.getenv("JEV_INTERCEPT_TRACE") != "1":
        return

    modules = tuple(
        item.strip()
        for item in os.getenv(
            "JEV_INTERCEPT_MODULES", "app.routers,app.services,app.models"
        ).split(",")
        if item.strip()
    )
    max_depth = int(os.getenv("JEV_INTERCEPT_TRACE_DEPTH", "3"))
    self_file = __file__

    def tracer(frame, event, arg):
        filename = frame.f_code.co_filename
        if (
            filename == self_file
            or "/site-packages/" in filename
            or "/venv/" in filename
        ):
            return None
        module = frame.f_globals.get("__name__", "")
        if not any(module == item or module.startswith(item + ".") for item in modules):
            return None
        if _trace_depth(frame) > max_depth:
            return None

        payload: dict[str, Any] = {
            "type": f"function_{event}",
            "module": module,
            "function": frame.f_code.co_name,
            "lineno": frame.f_lineno,
        }
        if event == "call":
            payload["args"] = {
                key: redact(value)
                for key, value in frame.f_locals.items()
                if not key.startswith("_")
            }
        elif event == "return":
            payload["return_value"] = redact(arg)
        elif event == "exception":
            payload["exception"] = str(arg[1]) if arg and len(arg) > 1 else ""
        _safe_write(payload)
        return tracer

    sys.settrace(tracer)
    logger.info("[jev-intercept] sys.settrace enabled")


def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._jev_query_start = time.perf_counter()
    _safe_write(
        {
            "type": "db_query_start",
            "statement": statement[:500],
            "params": redact(parameters),
        }
    )


def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    started = getattr(context, "_jev_query_start", None)
    duration = (time.perf_counter() - started) * 1000 if started else 0.0
    _safe_write(
        {
            "type": "db_query_end",
            "statement": statement[:500],
            "duration_ms": duration,
            "rowcount": cursor.rowcount,
        }
    )


def install_sqlalchemy_interceptor(engine) -> None:
    """Attach query listeners once per engine."""
    from sqlalchemy import event

    if not event.contains(engine, "before_cursor_execute", _before_cursor_execute):
        event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    if not event.contains(engine, "after_cursor_execute", _after_cursor_execute):
        event.listen(engine, "after_cursor_execute", _after_cursor_execute)


def install_interceptor(app) -> None:
    """Install middleware, optional tracing and SQLAlchemy listeners.

    Safe to call unconditionally: it is a no-op unless ``JEV_INTERCEPT=1``.
    """
    if not enabled():
        return

    app.add_middleware(InterceptMiddleware)
    install_tracing()
    try:
        from app.database import engine

        install_sqlalchemy_interceptor(engine)
    except Exception as exc:  # pragma: no cover - database may be unavailable
        logger.warning("[jev-intercept] SQLAlchemy hook skipped: %s", exc)
    logger.info("[jev-intercept] Installed on FastAPI app")
