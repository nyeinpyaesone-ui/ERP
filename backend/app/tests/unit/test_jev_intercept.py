"""Unit tests for the Jev-Intercept collector and middleware."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_db
from app.routers import jev_intercept
from app.services import jev_intercept as service

pytestmark = pytest.mark.unit


def _actor(*permissions: tuple[str, str]) -> SimpleNamespace:
    return SimpleNamespace(
        id=42,
        role="user",
        is_active=True,
        roles=[
            SimpleNamespace(
                permissions=[
                    SimpleNamespace(resource=resource, action=action)
                    for resource, action in permissions
                ]
            )
        ],
    )


@pytest.fixture
def events_path(tmp_path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("JEV_INTERCEPT_EVENTS_FILE", str(path))
    monkeypatch.delenv("JEV_INTERCEPT", raising=False)
    return path


@pytest.fixture
def client(events_path):
    app = FastAPI()
    app.include_router(jev_intercept.router, prefix="/api/v1/jev")
    app.dependency_overrides[get_db] = lambda: Mock()
    with TestClient(app) as test_client:
        yield app, test_client


def _authorize(app: FastAPI, actor: SimpleNamespace) -> None:
    app.dependency_overrides[get_current_user] = lambda: actor


def test_status_requires_read_permission(client) -> None:
    app, test_client = client
    _authorize(app, _actor())
    response = test_client.get("/api/v1/jev/intercept/status")
    assert response.status_code == 403
    assert response.json() == {"detail": "Permission denied: jev_intercept:read"}


def test_status_reports_path_and_count(client, events_path) -> None:
    app, test_client = client
    _authorize(app, _actor(("jev_intercept", "read")))
    events_path.write_text('{"type":"one"}\n{"type":"two"}\n', encoding="utf-8")

    response = test_client.get("/api/v1/jev/intercept/status")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "events_file": str(events_path),
        "events_count": 2,
    }


def test_collect_is_inert_when_interception_disabled(client, events_path) -> None:
    app, test_client = client
    _authorize(app, _actor(("jev_intercept", "create")))

    response = test_client.post("/api/v1/jev/intercept", json={"type": "render"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Jev interception is disabled"}
    assert not events_path.exists()


def test_collect_appends_event(client, events_path, monkeypatch) -> None:
    app, test_client = client
    _authorize(app, _actor(("jev_intercept", "create")))
    monkeypatch.setenv("JEV_INTERCEPT", "1")

    response = test_client.post(
        "/api/v1/jev/intercept",
        json={"type": "render", "component": "Dashboard"},
        headers={"x-request-id": "req-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    record = json.loads(events_path.read_text(encoding="utf-8").strip())
    assert record["type"] == "render"
    assert record["component"] == "Dashboard"
    assert record["source"] == "frontend"
    assert record["request_id"] == "req-1"


def test_collect_rejects_invalid_json(client, events_path, monkeypatch) -> None:
    app, test_client = client
    _authorize(app, _actor(("jev_intercept", "create")))
    monkeypatch.setenv("JEV_INTERCEPT", "1")

    response = test_client.post(
        "/api/v1/jev/intercept",
        content=b"not-json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json() == {"ok": False, "error": "invalid JSON body"}
    assert not events_path.exists()


def test_middleware_records_http_request(events_path) -> None:
    app = FastAPI()
    app.add_middleware(service.InterceptMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    @app.post("/login")
    async def login(request: Request):
        await request.json()
        return {"password": "hunter2", "ok": True}

    with TestClient(app) as test_client:
        assert test_client.get("/ping?q=1").status_code == 200
        assert (
            test_client.post("/login", json={"token": "abc", "user": "a"}).status_code
            == 200
        )

    first, second = (
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    )
    assert first["type"] == "http_request"
    assert first["method"] == "GET"
    assert first["path"] == "/ping"
    assert first["query_string"] == "q=1"
    assert first["response_status"] == 200

    assert second["path"] == "/login"
    assert second["request_body"] == {"token": "***", "user": "a"}
    assert second["response_body"] == {"password": "***", "ok": True}


def test_summarize_body_masks_form_encoded_secrets() -> None:
    summary = service.summarize_body(b"user=a&password=hunter2&token=abc")
    assert summary == "user=a&password=***&token=***"


def test_summarize_body_keeps_plain_text() -> None:
    assert service.summarize_body(b"plain text") == "plain text"
    assert service.summarize_body(b"") == ""


def test_install_interceptor_is_noop_when_disabled(events_path) -> None:
    app = FastAPI()
    service.install_interceptor(app)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    with TestClient(app) as test_client:
        assert test_client.get("/ping").status_code == 200

    assert not events_path.exists()
