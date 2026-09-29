from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from typing import Dict, List
import json
import asyncio

from app.auth import get_current_user_optional
from app.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        if client_id not in self.active_connections:
            self.active_connections[client_id] = []
        self.active_connections[client_id].append(websocket)

    def disconnect(self, websocket: WebSocket, client_id: str):
        if client_id in self.active_connections:
            self.active_connections[client_id].remove(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str, client_id: str = None):
        if client_id and client_id in self.active_connections:
            for connection in self.active_connections[client_id]:
                await connection.send_text(message)
        else:
            for connections in self.active_connections.values():
                for connection in connections:
                    await connection.send_text(message)

manager = ConnectionManager()

async def get_websocket_user(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """Return the active user identified by the token's subject.

    Token, subject-conversion, and database errors close the socket with code
    4001 and return None, as do missing or inactive users. Errors from closing
    the socket in the exception handler propagate.
    """
    from app.auth import decode_token
    from app.models import User
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            await websocket.close(code=4001, reason="Invalid or inactive user")
            return None
        return user
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return None

@router.websocket("/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """Authenticate a socket and exchange messages under the user's ID.

    The path's ``client_id`` is ignored. Ping receives pong; subscribe only
    acknowledges a channel. Other messages target the named connection group
    or the user's group by default; an unknown group broadcasts to everyone.
    Receive-loop errors remove the connection and are swallowed.
    """
    user = await get_websocket_user(websocket, token, db)
    if not user:
        return
    
    # Use user.id as the actual client_id for security
    await manager.connect(websocket, str(user.id))
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await manager.send_personal_message(
                    json.dumps({"type": "pong", "timestamp": str(asyncio.get_running_loop().time())}),
                    websocket
                )
            elif message.get("type") == "subscribe":
                channel = message.get("channel", "general")
                await manager.send_personal_message(
                    json.dumps({"type": "subscribed", "channel": channel}),
                    websocket
                )
            else:
                await manager.broadcast(
                    json.dumps({"type": "message", "data": message, "from": str(user.id)}),
                    message.get("channel", str(user.id))
                )
    except WebSocketDisconnect:
        manager.disconnect(websocket, str(user.id))
    except Exception:
        manager.disconnect(websocket, str(user.id))

@router.post("/broadcast")
async def broadcast_message(
    message: dict,
    current_user = Depends(get_current_user_optional)
):
    """Send the message as JSON to all connected clients and return sent status.

    Raise HTTP 401 without an authenticated user. Serialization and socket
    send errors propagate, possibly after some clients received the message.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    await manager.broadcast(json.dumps(message))
    return {"status": "sent"}

