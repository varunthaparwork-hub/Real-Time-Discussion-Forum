"""
Tests for ConnectionManager — WebSocket connection + thread subscription manager.
Covers: connect, disconnect, subscribe/unsubscribe, send_to_user, send_to_thread.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.connection_manager import ConnectionManager


@pytest.fixture
def cm():
    return ConnectionManager()


def make_ws():
    """Create a mock WebSocket with async methods and hashable identity."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    # Make hashable (needed for sets in thread_subscriptions)
    _id = id(ws)
    ws.__hash__ = MagicMock(return_value=_id)
    ws.__eq__ = MagicMock(side_effect=lambda other: ws is other)
    return ws


# ── connect ─────────────────────────────────────────────────────────


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, cm):
        ws = make_ws()
        await cm.connect(1, ws)
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_stores_in_user_connections(self, cm):
        ws = make_ws()
        await cm.connect(1, ws)
        assert ws in cm.user_connections[1]

    @pytest.mark.asyncio
    async def test_connect_multiple_sockets_same_user(self, cm):
        ws1 = make_ws()
        ws2 = make_ws()
        await cm.connect(1, ws1)
        await cm.connect(1, ws2)
        assert len(cm.user_connections[1]) == 2
        assert ws1 in cm.user_connections[1]
        assert ws2 in cm.user_connections[1]


# ── disconnect ──────────────────────────────────────────────────────


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_removes_socket(self, cm):
        ws = make_ws()
        await cm.connect(1, ws)
        cm.disconnect(1, ws)
        assert 1 not in cm.user_connections

    @pytest.mark.asyncio
    async def test_disconnect_cleans_thread_subscriptions(self, cm):
        ws = make_ws()
        await cm.connect(1, ws)
        cm.subscribe_thread(ws, 10)
        cm.subscribe_thread(ws, 20)
        cm.disconnect(1, ws)
        assert 10 not in cm.thread_subscriptions
        assert 20 not in cm.thread_subscriptions
        assert ws not in cm._socket_threads

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_is_safe(self, cm):
        ws = make_ws()
        cm.disconnect(999, ws)  # Should not raise

    @pytest.mark.asyncio
    async def test_disconnect_keeps_other_sockets(self, cm):
        ws1 = make_ws()
        ws2 = make_ws()
        await cm.connect(1, ws1)
        await cm.connect(1, ws2)
        cm.disconnect(1, ws1)
        assert ws2 in cm.user_connections[1]
        assert ws1 not in cm.user_connections[1]


# ── subscribe_thread ────────────────────────────────────────────────


class TestSubscribeThread:
    @pytest.mark.asyncio
    async def test_subscribe_adds_to_both_maps(self, cm):
        ws = make_ws()
        await cm.connect(1, ws)
        cm.subscribe_thread(ws, 5)
        assert ws in cm.thread_subscriptions[5]
        assert 5 in cm._socket_threads[ws]

    @pytest.mark.asyncio
    async def test_subscribe_multiple_threads(self, cm):
        ws = make_ws()
        await cm.connect(1, ws)
        cm.subscribe_thread(ws, 5)
        cm.subscribe_thread(ws, 10)
        assert ws in cm.thread_subscriptions[5]
        assert ws in cm.thread_subscriptions[10]
        assert cm._socket_threads[ws] == {5, 10}


# ── unsubscribe_thread ─────────────────────────────────────────────


class TestUnsubscribeThread:
    @pytest.mark.asyncio
    async def test_unsubscribe_removes_from_thread(self, cm):
        ws = make_ws()
        await cm.connect(1, ws)
        cm.subscribe_thread(ws, 5)
        cm.unsubscribe_thread(ws, 5)
        assert 5 not in cm.thread_subscriptions
        assert 5 not in cm._socket_threads.get(ws, set())

    @pytest.mark.asyncio
    async def test_unsubscribe_keeps_other_subscriptions(self, cm):
        ws = make_ws()
        await cm.connect(1, ws)
        cm.subscribe_thread(ws, 5)
        cm.subscribe_thread(ws, 10)
        cm.unsubscribe_thread(ws, 5)
        assert ws in cm.thread_subscriptions[10]
        assert 10 in cm._socket_threads.get(ws, set())
        assert 5 not in cm._socket_threads.get(ws, set())


# ── send_to_user ────────────────────────────────────────────────────


class TestSendToUser:
    @pytest.mark.asyncio
    async def test_send_to_user_sends_json(self, cm):
        ws = make_ws()
        await cm.connect(1, ws)
        await cm.send_to_user(1, {"hello": "world"})
        ws.send_json.assert_awaited_once_with({"hello": "world"})

    @pytest.mark.asyncio
    async def test_send_to_user_multiple_sockets(self, cm):
        ws1 = make_ws()
        ws2 = make_ws()
        await cm.connect(1, ws1)
        await cm.connect(1, ws2)
        await cm.send_to_user(1, {"data": 1})
        ws1.send_json.assert_awaited_once_with({"data": 1})
        ws2.send_json.assert_awaited_once_with({"data": 1})

    @pytest.mark.asyncio
    async def test_send_to_user_removes_stale_socket(self, cm):
        ws = make_ws()
        ws.send_json.side_effect = Exception("connection closed")
        await cm.connect(1, ws)
        await cm.send_to_user(1, {"data": 1})
        # Stale socket should be disconnected
        assert 1 not in cm.user_connections

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_user_is_safe(self, cm):
        await cm.send_to_user(999, {"data": 1})  # Should not raise


# ── send_to_thread ──────────────────────────────────────────────────


class TestSendToThread:
    @pytest.mark.asyncio
    async def test_send_to_thread_sends_json(self, cm):
        ws = make_ws()
        await cm.connect(1, ws)
        cm.subscribe_thread(ws, 5)
        await cm.send_to_thread(5, {"event": "new_comment"})
        ws.send_json.assert_awaited_once_with({"event": "new_comment"})

    @pytest.mark.asyncio
    async def test_send_to_thread_multiple_subscribers(self, cm):
        ws1 = make_ws()
        ws2 = make_ws()
        await cm.connect(1, ws1)
        await cm.connect(2, ws2)
        cm.subscribe_thread(ws1, 5)
        cm.subscribe_thread(ws2, 5)
        await cm.send_to_thread(5, {"event": "update"})
        ws1.send_json.assert_awaited_once_with({"event": "update"})
        ws2.send_json.assert_awaited_once_with({"event": "update"})

    @pytest.mark.asyncio
    async def test_send_to_thread_removes_stale_socket(self, cm):
        ws = make_ws()
        ws.send_json.side_effect = Exception("gone")
        await cm.connect(1, ws)
        cm.subscribe_thread(ws, 5)
        await cm.send_to_thread(5, {"event": "x"})
        assert ws not in cm.thread_subscriptions.get(5, set())

    @pytest.mark.asyncio
    async def test_send_to_unsubscribed_thread_is_safe(self, cm):
        await cm.send_to_thread(999, {"data": 1})  # Should not raise
