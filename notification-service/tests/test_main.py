"""
Tests for notification service main module.
Covers: health_check, _supervised_subscriber, _cleanup_old_notifications, lifespan.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import _supervised_subscriber, _cleanup_old_notifications, lifespan, app


# ── health check ────────────────────────────────────────────────────


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_returns_running(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.json() == {"status": "Notification Service Running"}


# ── _supervised_subscriber ──────────────────────────────────────────


class TestSupervisedSubscriber:
    @pytest.mark.asyncio
    async def test_catches_cancellation(self):
        with patch("app.main.start_redis_subscriber", new_callable=AsyncMock) as mock_sub:
            mock_sub.side_effect = asyncio.CancelledError()
            await _supervised_subscriber()  # Should not raise

    @pytest.mark.asyncio
    async def test_catches_general_exception(self):
        with patch("app.main.start_redis_subscriber", new_callable=AsyncMock) as mock_sub:
            mock_sub.side_effect = Exception("Redis connection failed")
            await _supervised_subscriber()  # Should not raise

    @pytest.mark.asyncio
    async def test_normal_run(self):
        with patch("app.main.start_redis_subscriber", new_callable=AsyncMock) as mock_sub:
            await _supervised_subscriber()
            mock_sub.assert_awaited_once()


# ── _cleanup_old_notifications ──────────────────────────────────────


def _mock_cleanup_session(rowcount=0, execute_side_effect=None):
    """Build a mock session + CM for cleanup tests."""
    mock_result = MagicMock()
    mock_result.rowcount = rowcount

    session = AsyncMock()
    if execute_side_effect:
        session.execute = AsyncMock(side_effect=execute_side_effect)
    else:
        session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return session, cm


class TestCleanupOldNotifications:
    @pytest.mark.asyncio
    async def test_deletes_old_notifications(self):
        session, cm = _mock_cleanup_session(rowcount=5)

        with patch("app.main.AsyncSessionLocal", return_value=cm), \
             patch("asyncio.sleep", new_callable=AsyncMock, side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await _cleanup_old_notifications()
            session.execute.assert_awaited_once()
            session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_old_notifications(self):
        session, cm = _mock_cleanup_session(rowcount=0)

        with patch("app.main.AsyncSessionLocal", return_value=cm), \
             patch("asyncio.sleep", new_callable=AsyncMock, side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await _cleanup_old_notifications()

    @pytest.mark.asyncio
    async def test_handles_db_error(self):
        _, cm = _mock_cleanup_session(execute_side_effect=Exception("DB error"))

        with patch("app.main.AsyncSessionLocal", return_value=cm), \
             patch("asyncio.sleep", new_callable=AsyncMock, side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await _cleanup_old_notifications()

    @pytest.mark.asyncio
    async def test_returns_on_cancel_during_db(self):
        _, cm = _mock_cleanup_session(execute_side_effect=asyncio.CancelledError)

        with patch("app.main.AsyncSessionLocal", return_value=cm):
            # CancelledError during DB op is caught inside the try block → return
            await _cleanup_old_notifications()  # Should return normally


# ── lifespan ────────────────────────────────────────────────────────


class TestLifespan:
    @pytest.mark.asyncio
    async def test_lifespan_starts_and_stops_tasks(self):
        with patch("app.main._supervised_subscriber", new_callable=AsyncMock), \
             patch("app.main._cleanup_old_notifications", new_callable=AsyncMock):
            async with lifespan(app):
                pass  # Tasks created and yielded
            # After exit, tasks should be cancelled without error
