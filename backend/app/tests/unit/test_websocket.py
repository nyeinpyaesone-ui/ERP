import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, WebSocketDisconnect

from app import auth
from app.routers import websocket

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("payload", [{}, {"sub": None}, {"sub": "invalid"}])
async def test_socket_rejects_malformed_subject(
    db: Mock, monkeypatch: pytest.MonkeyPatch, payload: dict
) -> None:
    monkeypatch.setattr(auth, "decode_token", Mock(return_value=payload))
    socket = AsyncMock()
    assert await websocket.get_websocket_user(socket, "token", db) is None
    socket.close.assert_awaited_once_with(code=4001, reason="Invalid token")
    db.query.assert_not_called()


async def test_socket_rejects_invalid_token(
    db: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        auth, "decode_token", Mock(side_effect=HTTPException(401, "Invalid token"))
    )
    socket = AsyncMock()
    assert await websocket.get_websocket_user(socket, "token", db) is None
    socket.close.assert_awaited_once_with(code=4001, reason="Invalid token")
    db.query.assert_not_called()


@pytest.mark.parametrize("user", [None, SimpleNamespace(id=42, is_active=False)])
async def test_socket_rejects_missing_or_disabled_user(
    db: Mock, monkeypatch: pytest.MonkeyPatch, user
) -> None:
    monkeypatch.setattr(auth, "decode_token", Mock(return_value={"sub": "42"}))
    db.query.return_value.first.return_value = user
    socket = AsyncMock()
    assert await websocket.get_websocket_user(socket, "token", db) is None
    socket.close.assert_awaited_once_with(code=4001, reason="Invalid or inactive user")


async def test_socket_resolves_active_user(
    db: Mock, actor: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth, "decode_token", Mock(return_value={"sub": "42"}))
    db.query.return_value.first.return_value = actor
    socket = AsyncMock()
    assert await websocket.get_websocket_user(socket, "token", db) is actor
    socket.close.assert_not_awaited()


@pytest.mark.parametrize("last_message", [WebSocketDisconnect(), "invalid-json"])
async def test_endpoint_uses_authenticated_identity_and_cleans_up(
    db: Mock,
    actor: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    last_message,
) -> None:
    monkeypatch.setattr(websocket, "get_websocket_user", AsyncMock(return_value=actor))
    manager = Mock(connect=AsyncMock(), broadcast=AsyncMock())
    monkeypatch.setattr(websocket, "manager", manager)
    socket = AsyncMock()
    socket.receive_text.side_effect = [json.dumps({"text": "hello"}), last_message]

    await websocket.websocket_endpoint(socket, "spoofed-user-id", "token", db)

    manager.connect.assert_awaited_once_with(socket, "42")
    message, channel = manager.broadcast.await_args.args
    assert json.loads(message) == {
        "type": "message",
        "data": {"text": "hello"},
        "from": "42",
    }
    assert channel == "42"
    manager.disconnect.assert_called_once_with(socket, "42")


async def test_endpoint_never_accepts_unauthenticated_socket(
    db: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(websocket, "get_websocket_user", AsyncMock(return_value=None))
    manager = Mock(connect=AsyncMock())
    monkeypatch.setattr(websocket, "manager", manager)
    await websocket.websocket_endpoint(AsyncMock(), "spoofed", "token", db)
    manager.connect.assert_not_awaited()


async def test_broadcast_requires_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = Mock(broadcast=AsyncMock())
    monkeypatch.setattr(websocket, "manager", manager)
    with pytest.raises(HTTPException) as error:
        await websocket.broadcast_message({"message": "hello"}, None)
    assert error.value.status_code == 401
    manager.broadcast.assert_not_awaited()
