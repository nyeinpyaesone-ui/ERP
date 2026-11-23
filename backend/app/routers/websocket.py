import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.auth import decode_token
from app.database import get_db
from app.models import User

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        self.active_connections.setdefault(client_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, client_id: str):
        connections = self.active_connections.get(client_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self.active_connections.pop(client_id, None)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str, client_id: str | None = None):
        if client_id:
            connections = list(self.active_connections.get(client_id, []))
        else:
            connections = [
                connection
                for group in self.active_connections.values()
                for connection in group
            ]
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception:
                # A disconnected socket is cleaned up by its receive loop.
                continue


manager = ConnectionManager()


def _authenticated_user(token: str, db: Session) -> User | None:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        return None
    return (
        db.query(User)
        .filter(User.id == int(user_id), User.is_active.is_(True))
        .first()
    )


@router.websocket("/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    db: Session = Depends(get_db),
):
    """Authenticate with a first-frame token; never accept credentials in URL query."""
    await websocket.accept()
    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        if (
            not isinstance(auth_message, dict)
            or auth_message.get("type") != "authenticate"
            or not isinstance(auth_message.get("token"), str)
        ):
            await websocket.close(code=4401, reason="Authentication required")
            return
        user = _authenticated_user(auth_message["token"], db)
        if not user:
            await websocket.close(code=4401, reason="Invalid or inactive user")
            return
    except asyncio.TimeoutError:
        await websocket.close(code=4408, reason="Authentication timeout")
        return
    except Exception:
        await websocket.close(code=4401, reason="Invalid authentication")
        return

    # The path client_id is intentionally ignored; authorization is bound to
    # the authenticated principal and no client can select another user's ID.
    authenticated_id = str(user.id)
    await manager.connect(websocket, authenticated_id)
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                await manager.send_personal_message(
                    json.dumps({"type": "error", "message": "Object message required"}),
                    websocket,
                )
                continue

            if message.get("type") == "ping":
                await manager.send_personal_message(
                    json.dumps(
                        {
                            "type": "pong",
                            "timestamp": str(asyncio.get_running_loop().time()),
                        }
                    ),
                    websocket,
                )
            elif message.get("type") == "subscribe":
                channel = str(message.get("channel", "general"))
                await manager.send_personal_message(
                    json.dumps({"type": "subscribed", "channel": channel}), websocket
                )
            else:
                # A user may only publish to their own channel. Global broadcast
                # is reserved for the authenticated HTTP endpoint below.
                await manager.broadcast(
                    json.dumps(
                        {"type": "message", "data": message, "from": authenticated_id}
                    ),
                    authenticated_id,
                )
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, authenticated_id)


@router.post("/broadcast")
async def broadcast_message(
    message: dict, current_user=Depends(__import__("app.auth", fromlist=["get_current_user_optional"]).get_current_user_optional)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    await manager.broadcast(json.dumps(message))
    return {"status": "sent"}
