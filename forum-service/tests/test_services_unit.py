"""
Unit tests for services: auth_client, event_publisher, redis_pool.
Also covers: main.py outbox_flusher, create_tables, create_indexes.

Uses importlib.reload() to restore real function implementations
that the conftest session-scoped patches replace.
"""
import asyncio
import importlib
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _reload_auth_client():
    """Reload to get original (un-patched) auth_client functions."""
    import app.services.auth_client as mod
    importlib.reload(mod)
    return mod


def _reload_event_publisher():
    import app.services.event_publisher as mod
    importlib.reload(mod)
    return mod


# =====================================================================
# auth_client
# =====================================================================
class TestAuthClient:

    @pytest.mark.asyncio
    async def test_get_user_map_empty_ids(self):
        mod = _reload_auth_client()
        result = await mod.get_user_map([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_user_map_all_cached(self):
        mod = _reload_auth_client()
        cached_user = json.dumps({"id": 1, "username": "cached_user", "avatar": None, "role": "member"})
        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=[cached_user])

        with patch.object(mod, "get_redis", return_value=mock_redis):
            result = await mod.get_user_map([1])
            assert result[1]["username"] == "cached_user"

    @pytest.mark.asyncio
    async def test_get_user_map_redis_down_fetches_all(self):
        mod = _reload_auth_client()
        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(side_effect=Exception("Redis down"))
        mock_pipe = MagicMock()
        mock_pipe.setex = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)  # sync call

        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1, "username": "fetched", "avatar": None, "role": "member"}]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch.object(mod, "get_redis", return_value=mock_redis), \
             patch.object(mod, "_get_http_client", return_value=mock_client):
            result = await mod.get_user_map([1])
            assert result[1]["username"] == "fetched"

    @pytest.mark.asyncio
    async def test_get_user_map_auth_service_down_placeholder(self):
        mod = _reload_auth_client()
        import httpx
        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=[None])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.is_closed = False

        with patch.object(mod, "get_redis", return_value=mock_redis), \
             patch.object(mod, "_get_http_client", return_value=mock_client):
            result = await mod.get_user_map([42])
            assert result[42]["username"] == "User#42"

    @pytest.mark.asyncio
    async def test_get_user_map_unexpected_error_placeholder(self):
        mod = _reload_auth_client()
        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=[None])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("unexpected"))
        mock_client.is_closed = False

        with patch.object(mod, "get_redis", return_value=mock_redis), \
             patch.object(mod, "_get_http_client", return_value=mock_client):
            result = await mod.get_user_map([42])
            assert result[42]["username"] == "User#42"

    @pytest.mark.asyncio
    async def test_get_user_map_partial_response_fills_placeholder(self):
        mod = _reload_auth_client()
        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=[None, None])
        mock_pipe = MagicMock()
        mock_pipe.setex = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1, "username": "alice", "avatar": None, "role": "member"}]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch.object(mod, "get_redis", return_value=mock_redis), \
             patch.object(mod, "_get_http_client", return_value=mock_client):
            result = await mod.get_user_map([1, 2])
            assert result[1]["username"] == "alice"
            assert result[2]["username"] == "User#2"

    @pytest.mark.asyncio
    async def test_get_user_role(self):
        mod = _reload_auth_client()
        with patch.object(mod, "get_user_map", new_callable=AsyncMock) as mock:
            mock.return_value = {1: {"id": 1, "username": "admin", "role": "admin"}}
            role = await mod.get_user_role(1)
            assert role == "admin"

    @pytest.mark.asyncio
    async def test_get_user_role_missing_user(self):
        mod = _reload_auth_client()
        with patch.object(mod, "get_user_map", new_callable=AsyncMock) as mock:
            mock.return_value = {}
            role = await mod.get_user_role(999)
            assert role == "member"

    @pytest.mark.asyncio
    async def test_get_users_by_usernames_empty(self):
        mod = _reload_auth_client()
        result = await mod.get_users_by_usernames([])
        assert result == []

    @pytest.mark.asyncio
    async def test_get_users_by_usernames_cached(self):
        mod = _reload_auth_client()
        cached = json.dumps({"id": 10, "username": "alice", "avatar": None, "role": "member"})
        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=[cached])

        with patch.object(mod, "get_redis", return_value=mock_redis):
            result = await mod.get_users_by_usernames(["alice"])
            assert result[0]["username"] == "alice"

    @pytest.mark.asyncio
    async def test_get_users_by_usernames_uncached_fetches(self):
        mod = _reload_auth_client()
        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=[None])
        mock_pipe = MagicMock()
        mock_pipe.setex = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 10, "username": "alice", "avatar": None, "role": "member"}]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch.object(mod, "get_redis", return_value=mock_redis), \
             patch.object(mod, "_get_http_client", return_value=mock_client):
            result = await mod.get_users_by_usernames(["alice"])
            assert result[0]["username"] == "alice"

    @pytest.mark.asyncio
    async def test_get_users_by_usernames_auth_down(self):
        mod = _reload_auth_client()
        import httpx
        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=[None])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.is_closed = False

        with patch.object(mod, "get_redis", return_value=mock_redis), \
             patch.object(mod, "_get_http_client", return_value=mock_client):
            result = await mod.get_users_by_usernames(["alice"])
            assert result == []

    @pytest.mark.asyncio
    async def test_get_users_by_usernames_redis_down(self):
        mod = _reload_auth_client()
        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(side_effect=Exception("Redis down"))
        mock_pipe = MagicMock()
        mock_pipe.setex = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 10, "username": "bob", "avatar": None, "role": "member"}]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch.object(mod, "get_redis", return_value=mock_redis), \
             patch.object(mod, "_get_http_client", return_value=mock_client):
            result = await mod.get_users_by_usernames(["bob"])
            assert result[0]["username"] == "bob"

    def test_placeholder_user(self):
        mod = _reload_auth_client()
        user = mod._placeholder_user(7)
        assert user["id"] == 7
        assert user["username"] == "User#7"
        assert user["role"] == "member"

    def test_get_http_client_creates_client(self):
        mod = _reload_auth_client()
        old = mod._http_client
        mod._http_client = None
        try:
            client = mod._get_http_client()
            assert client is not None
        finally:
            mod._http_client = old


# =====================================================================
# event_publisher
# =====================================================================
class TestEventPublisher:

    @pytest.mark.asyncio
    async def test_publish_event_success(self):
        mod = _reload_event_publisher()
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234-0")

        with patch.object(mod, "get_redis", return_value=mock_redis):
            await mod.publish_event({"event_type": "test"})
            mock_redis.xadd.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publish_event_redis_down_saves_outbox(self):
        mod = _reload_event_publisher()
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch.object(mod, "get_redis", return_value=mock_redis), \
             patch.object(mod, "_save_to_outbox", new_callable=AsyncMock) as mock_save:
            await mod.publish_event({"event_type": "test"})
            mock_save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_to_outbox(self):
        mod = _reload_event_publisher()
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.db.database.AsyncSessionLocal", return_value=cm):
            await mod._save_to_outbox({"event_type": "test"})
            session.add.assert_called_once()
            session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_to_outbox_db_error(self):
        mod = _reload_event_publisher()
        session = AsyncMock()
        session.add = MagicMock(side_effect=Exception("DB error"))

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.db.database.AsyncSessionLocal", return_value=cm):
            await mod._save_to_outbox({"event_type": "test"})

    @pytest.mark.asyncio
    async def test_flush_outbox_redis_down(self):
        mod = _reload_event_publisher()
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=ConnectionError("down"))

        with patch.object(mod, "get_redis", return_value=mock_redis):
            result = await mod.flush_outbox()
            assert result == 0

    @pytest.mark.asyncio
    async def test_flush_outbox_no_rows(self):
        mod = _reload_event_publisher()
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch.object(mod, "get_redis", return_value=mock_redis), \
             patch("app.db.database.AsyncSessionLocal", return_value=cm):
            result = await mod.flush_outbox()
            assert result == 0

    @pytest.mark.asyncio
    async def test_flush_outbox_flushes_rows(self):
        mod = _reload_event_publisher()
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="msg-1")

        row = MagicMock()
        row.channel = "forum_events_stream"
        row.payload = json.dumps({"event_type": "test"})

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [row]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)
        session.delete = AsyncMock()
        session.commit = AsyncMock()

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch.object(mod, "get_redis", return_value=mock_redis), \
             patch("app.db.database.AsyncSessionLocal", return_value=cm):
            result = await mod.flush_outbox()
            assert result == 1
            mock_redis.xadd.assert_awaited_once()
            session.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_flush_outbox_redis_fails_mid_flush(self):
        mod = _reload_event_publisher()
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.xadd = AsyncMock(side_effect=ConnectionError("Redis died"))

        row = MagicMock()
        row.channel = "forum_events_stream"
        row.payload = json.dumps({"event_type": "test"})

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [row]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch.object(mod, "get_redis", return_value=mock_redis), \
             patch("app.db.database.AsyncSessionLocal", return_value=cm):
            result = await mod.flush_outbox()
            assert result == 0


# =====================================================================
# redis_pool
# =====================================================================
class TestRedisPool:

    def test_dummy_redis_mget(self):
        from app.services.redis_pool import DummyRedis
        dummy = DummyRedis()
        result = asyncio.get_event_loop().run_until_complete(dummy.mget("a", "b"))
        assert result == [None, None]

    def test_dummy_redis_get(self):
        from app.services.redis_pool import DummyRedis
        dummy = DummyRedis()
        result = asyncio.get_event_loop().run_until_complete(dummy.get("key"))
        assert result is None

    def test_dummy_redis_setex(self):
        from app.services.redis_pool import DummyRedis
        dummy = DummyRedis()
        asyncio.get_event_loop().run_until_complete(dummy.setex("k", 60, "v"))

    def test_dummy_redis_xadd_raises(self):
        from app.services.redis_pool import DummyRedis
        dummy = DummyRedis()
        with pytest.raises(ConnectionError):
            asyncio.get_event_loop().run_until_complete(dummy.xadd("stream", {"data": "x"}))

    def test_dummy_redis_ping_raises(self):
        from app.services.redis_pool import DummyRedis
        dummy = DummyRedis()
        with pytest.raises(ConnectionError):
            asyncio.get_event_loop().run_until_complete(dummy.ping())

    def test_dummy_redis_publish_raises(self):
        from app.services.redis_pool import DummyRedis
        dummy = DummyRedis()
        with pytest.raises(ConnectionError):
            asyncio.get_event_loop().run_until_complete(dummy.publish("ch", "msg"))

    def test_dummy_pipeline_returns_self(self):
        from app.services.redis_pool import _DummyPipeline
        pipe = _DummyPipeline()
        assert pipe.setex("k", 60, "v") is pipe
        assert pipe.delete("k") is pipe

    def test_dummy_pipeline_execute(self):
        from app.services.redis_pool import _DummyPipeline
        pipe = _DummyPipeline()
        result = asyncio.get_event_loop().run_until_complete(pipe.execute())
        assert result == []

    def test_get_redis_with_pool(self):
        import app.services.redis_pool as mod
        old_pool = mod._pool
        old_dummy = mod._use_dummy
        mod._use_dummy = False
        mod._pool = MagicMock()
        try:
            with patch("redis.asyncio.Redis") as MockRedis:
                MockRedis.return_value = MagicMock()
                r = mod.get_redis()
                assert r is not None
        finally:
            mod._pool = old_pool
            mod._use_dummy = old_dummy

    def test_get_redis_dummy_when_no_pool(self):
        import app.services.redis_pool as mod
        old_pool = mod._pool
        old_dummy = mod._use_dummy
        mod._pool = None
        mod._use_dummy = True
        try:
            r = mod.get_redis()
            assert isinstance(r, mod.DummyRedis)
        finally:
            mod._pool = old_pool
            mod._use_dummy = old_dummy

    def test_init_pool_failure_sets_dummy(self):
        import app.services.redis_pool as mod
        old_pool = mod._pool
        old_dummy = mod._use_dummy
        try:
            with patch("redis.asyncio.ConnectionPool.from_url", side_effect=Exception("fail")):
                mod._init_pool()
            assert mod._use_dummy is True
        finally:
            mod._pool = old_pool
            mod._use_dummy = old_dummy


# =====================================================================
# main.py
# =====================================================================
class TestMainModule:

    @pytest.mark.asyncio
    async def test_outbox_flusher_runs_and_handles_error(self):
        """flush_outbox is imported locally inside _outbox_flusher,
        so patch at the source module level."""
        import app.main as main_mod
        importlib.reload(main_mod)
        call_count = 0

        async def mock_flush():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Flush error")
            raise asyncio.CancelledError()

        with patch("app.services.event_publisher.flush_outbox", side_effect=mock_flush), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(asyncio.CancelledError):
                await main_mod._outbox_flusher()
            assert call_count >= 1


# =====================================================================
# create_tables / create_indexes
# =====================================================================
class TestCreateScripts:

    @pytest.mark.asyncio
    async def test_create_tables(self):
        mock_conn = AsyncMock()
        mock_conn.run_sync = AsyncMock()

        mock_begin = AsyncMock()
        mock_begin.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_begin.__aexit__ = AsyncMock(return_value=False)

        # Patch engine at the source (app.db.database), then re-import
        # so the module picks up the mock engine
        with patch("app.db.database.engine") as mock_engine:
            mock_engine.begin.return_value = mock_begin
            import app.create_tables
            importlib.reload(app.create_tables)
            await app.create_tables.create_tables()
            mock_conn.run_sync.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_indexes(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_begin = AsyncMock()
        mock_begin.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_begin.__aexit__ = AsyncMock(return_value=False)

        with patch("app.db.database.engine") as mock_engine:
            mock_engine.begin.return_value = mock_begin
            import app.create_indexes
            importlib.reload(app.create_indexes)
            await app.create_indexes.create_indexes()
            assert mock_conn.execute.await_count >= 9
