"""
Tests for event_consumer — Redis Stream consumer with consumer groups.
Covers: handle_event, _ensure_consumer_group, _process_pending, start_redis_subscriber.
"""
import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.event_consumer import (
    handle_event,
    _ensure_consumer_group,
    _process_pending,
    start_redis_subscriber,
    STREAM_NAME,
    GROUP_NAME,
)


def _mock_db_session(execute_return=None, execute_side_effect=None):
    """Helper: build a mock async session + context manager."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    if execute_side_effect:
        session.execute = AsyncMock(side_effect=execute_side_effect)
    elif execute_return:
        session.execute = AsyncMock(return_value=execute_return)

    async def _refresh(obj):
        obj.id = 42
        obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

    session.refresh = AsyncMock(side_effect=_refresh)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return session, cm


# ── handle_event ────────────────────────────────────────────────────


class TestHandleEvent:
    @pytest.mark.asyncio
    async def test_thread_broadcast_no_target_user(self):
        """Events with no target_user_id broadcast to thread room."""
        event = {"event_type": "comment.created", "thread_id": 5}
        with patch("app.services.event_consumer.manager") as mgr:
            mgr.send_to_thread = AsyncMock()
            await handle_event(event)
            mgr.send_to_thread.assert_awaited_once_with(5, event)

    @pytest.mark.asyncio
    async def test_thread_broadcast_explicit_none_target(self):
        event = {"event_type": "comment.created", "thread_id": 5, "target_user_id": None}
        with patch("app.services.event_consumer.manager") as mgr:
            mgr.send_to_thread = AsyncMock()
            await handle_event(event)
            mgr.send_to_thread.assert_awaited_once_with(5, event)

    @pytest.mark.asyncio
    async def test_broadcast_without_thread_id_is_safe(self):
        event = {"event_type": "comment.created"}
        with patch("app.services.event_consumer.manager") as mgr:
            mgr.send_to_thread = AsyncMock()
            await handle_event(event)
            mgr.send_to_thread.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_all_like_events_broadcast(self):
        for etype in ["thread.liked", "thread.unliked", "comment.liked", "comment.unliked"]:
            event = {"event_type": etype, "thread_id": 7}
            with patch("app.services.event_consumer.manager") as mgr:
                mgr.send_to_thread = AsyncMock()
                await handle_event(event)
                mgr.send_to_thread.assert_awaited_once_with(7, event)

    @pytest.mark.asyncio
    async def test_personal_notification_saved_and_sent(self):
        event = {
            "event_type": "comment.created",
            "target_user_id": 1,
            "title": "New comment",
            "message": "User X commented",
            "thread_id": 5,
            "comment_id": 10,
            "action_user_id": 2,
        }
        session, cm = _mock_db_session()

        with patch("app.services.event_consumer.AsyncSessionLocal", return_value=cm), \
             patch("app.services.event_consumer.manager") as mgr:
            mgr.send_to_user = AsyncMock()
            mgr.send_to_thread = AsyncMock()
            await handle_event(event)

            session.add.assert_called_once()
            session.commit.assert_awaited_once()
            session.refresh.assert_awaited_once()
            mgr.send_to_user.assert_awaited_once()

            # Verify message contents
            user_id_arg, msg = mgr.send_to_user.call_args[0]
            assert user_id_arg == 1
            assert msg["event_type"] == "comment.created"
            assert msg["notification_id"] == 42
            assert msg["title"] == "New comment"

    @pytest.mark.asyncio
    async def test_personal_notification_skips_broadcast(self):
        event = {
            "event_type": "comment.created",
            "target_user_id": 1,
            "thread_id": 5,
            "title": "X",
            "message": "Y",
        }
        session, cm = _mock_db_session()

        with patch("app.services.event_consumer.AsyncSessionLocal", return_value=cm), \
             patch("app.services.event_consumer.manager") as mgr:
            mgr.send_to_thread = AsyncMock()
            mgr.send_to_user = AsyncMock()
            await handle_event(event)
            mgr.send_to_thread.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_personal_notification_db_error_caught(self):
        event = {
            "event_type": "comment.created",
            "target_user_id": 1,
            "title": "X",
            "message": "Y",
        }
        session, cm = _mock_db_session()
        session.add = MagicMock(side_effect=Exception("DB error"))

        with patch("app.services.event_consumer.AsyncSessionLocal", return_value=cm), \
             patch("app.services.event_consumer.manager"):
            await handle_event(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_unknown_event_type_no_broadcast(self):
        event = {"event_type": "unknown.event"}
        with patch("app.services.event_consumer.manager") as mgr:
            mgr.send_to_thread = AsyncMock()
            await handle_event(event)
            mgr.send_to_thread.assert_not_awaited()


# ── _ensure_consumer_group ──────────────────────────────────────────


class TestEnsureConsumerGroup:
    @pytest.mark.asyncio
    async def test_create_new_group(self):
        redis = AsyncMock()
        redis.xgroup_create = AsyncMock()
        await _ensure_consumer_group(redis)
        redis.xgroup_create.assert_awaited_once_with(
            STREAM_NAME, GROUP_NAME, id="0", mkstream=True
        )

    @pytest.mark.asyncio
    async def test_busygroup_ignored(self):
        redis = AsyncMock()
        redis.xgroup_create = AsyncMock(
            side_effect=Exception("BUSYGROUP Consumer Group name already exists")
        )
        await _ensure_consumer_group(redis)  # Should not raise

    @pytest.mark.asyncio
    async def test_other_error_propagates(self):
        redis = AsyncMock()
        redis.xgroup_create = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        with pytest.raises(Exception, match="Connection refused"):
            await _ensure_consumer_group(redis)


# ── _process_pending ────────────────────────────────────────────────


class TestProcessPending:
    @pytest.mark.asyncio
    async def test_no_pending_events(self):
        redis = AsyncMock()
        redis.xreadgroup = AsyncMock(return_value=[])
        await _process_pending(redis)
        redis.xreadgroup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_messages_list(self):
        redis = AsyncMock()
        redis.xreadgroup = AsyncMock(return_value=[("stream", [])])
        await _process_pending(redis)

    @pytest.mark.asyncio
    async def test_pending_events_processed_and_acked(self):
        data = json.dumps({"event_type": "comment.created", "thread_id": 1})
        redis = AsyncMock()
        redis.xreadgroup = AsyncMock(side_effect=[
            [("stream", [("msg-1", {"data": data})])],
            [],
        ])
        redis.xack = AsyncMock()

        with patch("app.services.event_consumer.handle_event", new_callable=AsyncMock) as h:
            await _process_pending(redis)
            h.assert_awaited_once()
            redis.xack.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_corrupt_json_acked_to_skip(self):
        redis = AsyncMock()
        redis.xreadgroup = AsyncMock(side_effect=[
            [("stream", [("msg-1", {"data": "not-valid-json"})])],
            [],
        ])
        redis.xack = AsyncMock()
        await _process_pending(redis)
        redis.xack.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handler_error_stops_processing(self):
        data = json.dumps({"event_type": "test"})
        redis = AsyncMock()
        # break in the for-loop only exits the for; while True loops back,
        # so the second xreadgroup call must return [] to end the function.
        redis.xreadgroup = AsyncMock(side_effect=[
            [("stream", [("msg-1", {"data": data}), ("msg-2", {"data": data})])],
            [],
        ])
        redis.xack = AsyncMock()

        with patch("app.services.event_consumer.handle_event", new_callable=AsyncMock) as h:
            h.side_effect = Exception("processing error")
            await _process_pending(redis)
            assert h.await_count == 1
            redis.xack.assert_not_awaited()


# ── start_redis_subscriber ──────────────────────────────────────────


class TestStartRedisSubscriber:
    @pytest.mark.asyncio
    async def test_cancellation_exits_cleanly(self):
        with patch("app.services.event_consumer.Redis") as MockRedis:
            mock_redis = AsyncMock()
            MockRedis.from_url.return_value = mock_redis
            mock_redis.ping = AsyncMock(side_effect=asyncio.CancelledError)
            mock_redis.close = AsyncMock()

            await start_redis_subscriber()  # Should exit, not hang

    @pytest.mark.asyncio
    async def test_connection_error_reconnects_with_backoff(self):
        call_count = 0

        with patch("app.services.event_consumer.Redis") as MockRedis:
            mock_redis = AsyncMock()
            MockRedis.from_url.return_value = mock_redis

            async def ping_effect():
                nonlocal call_count
                call_count += 1
                if call_count >= 2:
                    raise asyncio.CancelledError()
                raise ConnectionError("refused")

            mock_redis.ping = AsyncMock(side_effect=ping_effect)
            mock_redis.close = AsyncMock()

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await start_redis_subscriber()

            assert call_count >= 2

    @pytest.mark.asyncio
    async def test_processes_new_events_then_exits(self):
        event_data = json.dumps({"event_type": "test", "thread_id": 1})

        with patch("app.services.event_consumer.Redis") as MockRedis, \
             patch("app.services.event_consumer._ensure_consumer_group", new_callable=AsyncMock), \
             patch("app.services.event_consumer._process_pending", new_callable=AsyncMock), \
             patch("app.services.event_consumer.handle_event", new_callable=AsyncMock) as mock_h:

            mock_redis = AsyncMock()
            MockRedis.from_url.return_value = mock_redis
            mock_redis.ping = AsyncMock()

            call_count = 0

            async def xreadgroup_effect(**kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return [("stream", [("msg-1", {"data": event_data})])]
                raise asyncio.CancelledError()

            mock_redis.xreadgroup = AsyncMock(side_effect=xreadgroup_effect)
            mock_redis.xack = AsyncMock()
            mock_redis.close = AsyncMock()

            await start_redis_subscriber()
            mock_h.assert_awaited()
            mock_redis.xack.assert_awaited()
