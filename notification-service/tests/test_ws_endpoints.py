"""
Tests for WebSocket endpoints (ws.py).
Calls route functions directly with mocked WebSocket objects.
Covers: /ws (auth, subscribe, unsubscribe, non-JSON), /ws/test.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import WebSocketDisconnect

from app.routers.ws import websocket_unified, websocket_test


# ── /ws endpoint ────────────────────────────────────────────────────


class TestWebSocketUnified:
    @pytest.mark.asyncio
    async def test_missing_token_closes_4001(self):
        ws = AsyncMock()
        ws.query_params = {}
        ws.close = AsyncMock()

        await websocket_unified(ws)
        ws.close.assert_awaited_once_with(code=4001, reason="Missing token")

    @pytest.mark.asyncio
    async def test_invalid_token_closes_4003(self):
        ws = AsyncMock()
        ws.query_params = {"token": "bad.token"}
        ws.close = AsyncMock()

        with patch("app.routers.ws.decode_ws_token", return_value=None):
            await websocket_unified(ws)
        ws.close.assert_awaited_once_with(code=4003, reason="Invalid or expired token")

    @pytest.mark.asyncio
    async def test_valid_token_connects_then_disconnect(self):
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with patch("app.routers.ws.decode_ws_token", return_value=42), \
             patch("app.routers.ws.manager") as mgr:
            mgr.connect = AsyncMock()
            mgr.disconnect = MagicMock()

            await websocket_unified(ws)
            mgr.connect.assert_awaited_once_with(42, ws)
            mgr.disconnect.assert_called_once_with(42, ws)

    @pytest.mark.asyncio
    async def test_subscribe_thread_action(self):
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps({"action": "subscribe_thread", "thread_id": 5}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        with patch("app.routers.ws.decode_ws_token", return_value=1), \
             patch("app.routers.ws.manager") as mgr:
            mgr.connect = AsyncMock()
            mgr.disconnect = MagicMock()
            mgr.subscribe_thread = MagicMock()

            await websocket_unified(ws)
            mgr.subscribe_thread.assert_called_once_with(ws, 5)
            ws.send_json.assert_any_call({"action": "subscribed", "thread_id": 5})

    @pytest.mark.asyncio
    async def test_unsubscribe_thread_action(self):
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps({"action": "unsubscribe_thread", "thread_id": 10}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        with patch("app.routers.ws.decode_ws_token", return_value=1), \
             patch("app.routers.ws.manager") as mgr:
            mgr.connect = AsyncMock()
            mgr.disconnect = MagicMock()
            mgr.unsubscribe_thread = MagicMock()

            await websocket_unified(ws)
            mgr.unsubscribe_thread.assert_called_once_with(ws, 10)
            ws.send_json.assert_any_call({"action": "unsubscribed", "thread_id": 10})

    @pytest.mark.asyncio
    async def test_non_json_message_ignored(self):
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        ws.receive_text = AsyncMock(side_effect=[
            "plain text — not JSON",
            json.dumps({"action": "subscribe_thread", "thread_id": 1}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        with patch("app.routers.ws.decode_ws_token", return_value=1), \
             patch("app.routers.ws.manager") as mgr:
            mgr.connect = AsyncMock()
            mgr.disconnect = MagicMock()
            mgr.subscribe_thread = MagicMock()

            await websocket_unified(ws)
            # Should have processed subscribe after ignoring plain text
            mgr.subscribe_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_action_ignored(self):
        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps({"action": "do_something_weird", "thread_id": 1}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        with patch("app.routers.ws.decode_ws_token", return_value=1), \
             patch("app.routers.ws.manager") as mgr:
            mgr.connect = AsyncMock()
            mgr.disconnect = MagicMock()
            mgr.subscribe_thread = MagicMock()
            mgr.unsubscribe_thread = MagicMock()

            await websocket_unified(ws)
            mgr.subscribe_thread.assert_not_called()
            mgr.unsubscribe_thread.assert_not_called()


# ── /ws/test endpoint ───────────────────────────────────────────────


class TestWebSocketTestEndpoint:
    @pytest.mark.asyncio
    async def test_ws_test_connects_and_sends_message(self):
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        await websocket_test(ws)
        ws.accept.assert_awaited_once()
        ws.send_json.assert_awaited_once_with({"message": "connected"})
