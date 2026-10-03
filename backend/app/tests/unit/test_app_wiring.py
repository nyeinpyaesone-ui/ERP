from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


@pytest.fixture
def application(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # StaticFiles checks the directory when main is imported; keep it disposable.
    (tmp_path / "static").mkdir()
    monkeypatch.chdir(tmp_path)
    from app.main import app

    return app


async def test_lifespan_does_not_create_database_schema(
    application, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.database import Base
    from app.main import lifespan

    create = Mock(side_effect=AssertionError("Schema creation belongs to migrations"))
    monkeypatch.setattr(Base.metadata, "create_all", create)
    async with lifespan(application):
        pass
    create.assert_not_called()


@pytest.mark.parametrize("path", ["/health", "/api/v1/health"])
def test_liveness_registered_at_root_and_versioned_path(application, path: str) -> None:
    with TestClient(application) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.parametrize(
    "path", ["/api/v1/permissions/roles", "/api/v1/search/", "/api/v1/llm/models"]
)
def test_router_prefix_is_applied_once(application, path: str) -> None:
    with TestClient(application) as client:
        response = client.get(path)
        duplicated = client.get("/api/v1" + path)
    assert response.status_code == 401
    assert duplicated.status_code == 404


@pytest.mark.parametrize(
    "origin,allowed",
    [
        ("http://localhost:3000", True),
        ("http://localhost:5173", True),
        ("https://untrusted.example", False),
    ],
)
def test_cors_limits_credentialed_requests_to_allowed_origins(
    application, origin: str, allowed: bool
) -> None:
    with TestClient(application) as client:
        response = client.options(
            "/api/v1/auth/me",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
    assert response.status_code == (200 if allowed else 400)
    assert response.headers.get("access-control-allow-origin") == (
        origin if allowed else None
    )
