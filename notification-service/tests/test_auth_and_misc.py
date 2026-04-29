"""
Tests for REST auth edge cases and create_tables script.
Covers: missing user_id, invalid token, expired token (auth.py lines 29, 35-36),
        create_tables function (create_tables.py lines 6-19).
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from jose import jwt


SECRET = "my_very_long_super_secure_secret_key_2026_abc123"
ALGORITHM = "HS256"


# ── REST auth edge cases ────────────────────────────────────────────


class TestAuthEdgeCases:
    @pytest.mark.asyncio
    async def test_token_missing_user_id_returns_401(self, client):
        """JWT with no user_id claim → 401."""
        token = jwt.encode(
            {"role": "member", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            SECRET, algorithm=ALGORITHM,
        )
        resp = await client.get(
            "/notifications/", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_completely_invalid_token_returns_401(self, client):
        resp = await client.get(
            "/notifications/",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, client):
        token = jwt.encode(
            {"user_id": 1, "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            SECRET, algorithm=ALGORITHM,
        )
        resp = await client.get(
            "/notifications/", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401


# ── create_tables ───────────────────────────────────────────────────


class TestCreateTables:
    @pytest.mark.asyncio
    async def test_create_tables_runs_metadata_create_all(self):
        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock()

        mock_begin = AsyncMock()
        mock_begin.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_begin.__aexit__ = AsyncMock(return_value=False)

        with patch("app.create_tables.engine") as mock_engine:
            mock_engine.begin.return_value = mock_begin
            from app.create_tables import create_tables
            await create_tables()
            mock_conn.run_sync.assert_awaited_once()
