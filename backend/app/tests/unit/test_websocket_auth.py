from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.database import get_db
from app.routers import websocket as websocket_router


@pytest.fixture
def websocket_app():
    app = FastAPI()
    app.include_router(websocket_router.router, prefix="/api/v1/ws")
    db = Mock()
    app.dependency_overrides[get_db] = lambda: db
    return app, db


def test_websocket_authenticates_from_first_frame_not_query_string(
    websocket_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, db = websocket_app
    user = SimpleNamespace(id=42, is_active=True)
    db.query.return_value.filter.return_value.first.return_value = user
    monkeypatch.setattr(websocket_router, "decode_token", lambda token: {"sub": "42"})

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/client-ignored?token=not-used") as socket:
            socket.send_json({"type": "authenticate", "token": "valid-token"})
            socket.send_json({"type": "ping"})
            assert socket.receive_json()["type"] == "pong"


def test_websocket_rejects_query_token_without_authentication_frame(
    websocket_app,
) -> None:
    app, _ = websocket_app
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("/api/v1/ws/42?token=valid-token") as socket:
                socket.send_json({"type": "ping"})
        assert error.value.code == 4401


def test_websocket_rejects_invalid_first_frame(
    websocket_app,
) -> None:
    app, _ = websocket_app
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("/api/v1/ws/42") as socket:
                socket.send_json({"type": "ping"})
        assert error.value.code == 4401
