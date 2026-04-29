import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.connection_manager import manager
from app.core.ws_auth import decode_ws_token

logger = logging.getLogger("ws_router")

router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws")
async def websocket_unified(websocket: WebSocket):
    """
    Single WebSocket endpoint for all real-time communication.
    Handles personal notifications + thread subscriptions via messages:
      { "action": "subscribe_thread",   "thread_id": 5 }
      { "action": "unsubscribe_thread", "thread_id": 5 }
    """
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    user_id = decode_ws_token(token)
    if user_id is None:
        await websocket.close(code=4003, reason="Invalid or expired token")
        return

    await manager.connect(user_id, websocket)

    try:
        while True:
            raw = await websocket.receive_text()

            # Try to parse as JSON command
            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue  # ignore non-JSON messages (e.g. "hello" ping)

            action = msg.get("action")
            thread_id = msg.get("thread_id")

            if action == "subscribe_thread" and thread_id is not None:
                manager.subscribe_thread(websocket, int(thread_id))
                await websocket.send_json({"action": "subscribed", "thread_id": thread_id})

            elif action == "unsubscribe_thread" and thread_id is not None:
                manager.unsubscribe_thread(websocket, int(thread_id))
                await websocket.send_json({"action": "unsubscribed", "thread_id": thread_id})

    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)


@router.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"message": "connected"})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass