"""
Extended API tests for forum-service — covers uncovered router paths.
Focuses on: comment CRUD edge cases, like-comment flow, thread
update/delete forbidden, nested delete cascading, batch endpoints.
"""
import pytest


# =====================================================================
# Comment Router — Extra Paths
# =====================================================================
class TestCommentRouterExtra:

    @pytest.mark.asyncio
    async def test_get_single_comment(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        c = await client.post("/comments/", json={"content": "Hello", "thread_id": tid}, headers=auth_headers(user_id=1))
        cid = c.json()["id"]
        resp = await client.get(f"/comments/{cid}")
        assert resp.status_code == 200
        assert resp.json()["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_get_single_comment_not_found(self, client):
        resp = await client.get("/comments/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_comments_nonexistent_thread(self, client):
        resp = await client.get("/comments/thread/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_comment_not_found(self, client, auth_headers):
        resp = await client.put("/comments/99999", json={"content": "X"}, headers=auth_headers(user_id=1))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_comment_forbidden_other_user(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        c = await client.post("/comments/", json={"content": "Mine", "thread_id": tid}, headers=auth_headers(user_id=100))
        cid = c.json()["id"]
        resp = await client.put(f"/comments/{cid}", json={"content": "Hacked"}, headers=auth_headers(user_id=999))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_comment_not_found(self, client, auth_headers):
        resp = await client.delete("/comments/99999", headers=auth_headers(user_id=1))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_comment_forbidden_other_user(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        c = await client.post("/comments/", json={"content": "Mine", "thread_id": tid}, headers=auth_headers(user_id=200))
        cid = c.json()["id"]
        resp = await client.delete(f"/comments/{cid}", headers=auth_headers(user_id=999))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_comment_cascades_children(self, client, auth_headers):
        """Deleting parent deletes all nested replies and their likes."""
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        parent = await client.post("/comments/", json={"content": "Parent", "thread_id": tid}, headers=auth_headers(user_id=300))
        pid = parent.json()["id"]
        child = await client.post("/comments/", json={"content": "Child", "thread_id": tid, "parent_id": pid}, headers=auth_headers(user_id=301))
        child_id = child.json()["id"]

        # Like the child comment
        await client.post(f"/likes/comment/{child_id}", headers=auth_headers(user_id=302))

        # Delete parent → should cascade
        resp = await client.delete(f"/comments/{pid}", headers=auth_headers(user_id=300))
        assert resp.status_code == 200

        # Child should be gone
        assert (await client.get(f"/comments/{child_id}")).status_code == 404

    @pytest.mark.asyncio
    async def test_create_comment_with_mention(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        resp = await client.post(
            "/comments/",
            json={"content": "Hey @alice check this out", "thread_id": tid},
            headers=auth_headers(user_id=2),
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_reply_invalid_parent_id(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        resp = await client.post(
            "/comments/",
            json={"content": "Reply", "thread_id": tid, "parent_id": 99999},
            headers=auth_headers(user_id=2),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_reply_parent_wrong_thread(self, client, auth_headers):
        t1 = await client.post("/threads/", json={"title": "T1", "description": "D"}, headers=auth_headers(user_id=1))
        t2 = await client.post("/threads/", json={"title": "T2", "description": "D"}, headers=auth_headers(user_id=1))
        tid1 = t1.json()["id"]
        tid2 = t2.json()["id"]
        c = await client.post("/comments/", json={"content": "In T1", "thread_id": tid1}, headers=auth_headers(user_id=1))
        cid = c.json()["id"]
        resp = await client.post(
            "/comments/",
            json={"content": "Reply in T2", "thread_id": tid2, "parent_id": cid},
            headers=auth_headers(user_id=2),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_create_comment_same_user_as_thread_no_crash(self, client, auth_headers):
        """Comment by thread owner should NOT trigger notification to self."""
        t = await client.post("/threads/", json={"title": "My Thread", "description": "D"}, headers=auth_headers(user_id=500))
        tid = t.json()["id"]
        resp = await client.post("/comments/", json={"content": "My own comment", "thread_id": tid}, headers=auth_headers(user_id=500))
        assert resp.status_code == 201


# =====================================================================
# Like Router — Comment Likes
# =====================================================================
class TestCommentLikeEndpoints:

    @pytest.mark.asyncio
    async def test_like_comment(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        c = await client.post("/comments/", json={"content": "C", "thread_id": tid}, headers=auth_headers(user_id=1))
        cid = c.json()["id"]
        resp = await client.post(f"/likes/comment/{cid}", headers=auth_headers(user_id=2))
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_like_comment_not_found(self, client, auth_headers):
        resp = await client.post("/likes/comment/99999", headers=auth_headers(user_id=1))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_like_comment_duplicate_rejected(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        c = await client.post("/comments/", json={"content": "C", "thread_id": tid}, headers=auth_headers(user_id=1))
        cid = c.json()["id"]
        await client.post(f"/likes/comment/{cid}", headers=auth_headers(user_id=400))
        resp = await client.post(f"/likes/comment/{cid}", headers=auth_headers(user_id=400))
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_unlike_comment(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        c = await client.post("/comments/", json={"content": "C", "thread_id": tid}, headers=auth_headers(user_id=1))
        cid = c.json()["id"]
        await client.post(f"/likes/comment/{cid}", headers=auth_headers(user_id=401))
        resp = await client.delete(f"/likes/comment/{cid}", headers=auth_headers(user_id=401))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_unlike_comment_not_liked_404(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        c = await client.post("/comments/", json={"content": "C", "thread_id": tid}, headers=auth_headers(user_id=1))
        cid = c.json()["id"]
        resp = await client.delete(f"/likes/comment/{cid}", headers=auth_headers(user_id=402))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_comment_like_count(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        c = await client.post("/comments/", json={"content": "C", "thread_id": tid}, headers=auth_headers(user_id=1))
        cid = c.json()["id"]
        await client.post(f"/likes/comment/{cid}", headers=auth_headers(user_id=410))
        await client.post(f"/likes/comment/{cid}", headers=auth_headers(user_id=411))
        resp = await client.get(f"/likes/comment/{cid}/count")
        assert resp.status_code == 200
        assert resp.json()["like_count"] == 2

    @pytest.mark.asyncio
    async def test_comment_like_count_not_found(self, client):
        resp = await client.get("/likes/comment/99999/count")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_comment_like_status(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        c = await client.post("/comments/", json={"content": "C", "thread_id": tid}, headers=auth_headers(user_id=1))
        cid = c.json()["id"]
        resp = await client.get(f"/likes/comment/{cid}/status", headers=auth_headers(user_id=420))
        assert resp.json()["has_liked"] is False
        await client.post(f"/likes/comment/{cid}", headers=auth_headers(user_id=420))
        resp = await client.get(f"/likes/comment/{cid}/status", headers=auth_headers(user_id=420))
        assert resp.json()["has_liked"] is True

    @pytest.mark.asyncio
    async def test_batch_comment_like_counts_with_data(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        c = await client.post("/comments/", json={"content": "C", "thread_id": tid}, headers=auth_headers(user_id=1))
        cid = c.json()["id"]
        await client.post(f"/likes/comment/{cid}", headers=auth_headers(user_id=430))
        resp = await client.get(f"/likes/comments/counts?ids={cid}")
        assert resp.status_code == 200
        assert resp.json()["counts"][str(cid)] == 1

    @pytest.mark.asyncio
    async def test_batch_comment_like_statuses(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=1))
        tid = t.json()["id"]
        c = await client.post("/comments/", json={"content": "C", "thread_id": tid}, headers=auth_headers(user_id=1))
        cid = c.json()["id"]
        resp = await client.get(f"/likes/comments/statuses?ids={cid}", headers=auth_headers(user_id=440))
        assert resp.status_code == 200
        assert resp.json()["statuses"][str(cid)] is False

    @pytest.mark.asyncio
    async def test_batch_comment_statuses_empty_ids(self, client, auth_headers):
        resp = await client.get("/likes/comments/statuses?ids=", headers=auth_headers(user_id=1))
        assert resp.status_code == 200
        assert resp.json()["statuses"] == {}

    @pytest.mark.asyncio
    async def test_batch_comment_statuses_invalid_ids(self, client, auth_headers):
        resp = await client.get("/likes/comments/statuses?ids=abc", headers=auth_headers(user_id=1))
        assert resp.status_code == 400


# =====================================================================
# Thread Router — Extra Paths
# =====================================================================
class TestThreadRouterExtra:

    @pytest.mark.asyncio
    async def test_like_nonexistent_thread(self, client, auth_headers):
        resp = await client.post("/likes/thread/99999", headers=auth_headers(user_id=1))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_thread_like_count_nonexistent(self, client):
        resp = await client.get("/likes/thread/99999/count")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_nonexistent_thread(self, client, auth_headers):
        resp = await client.put("/threads/99999", json={"title": "X"}, headers=auth_headers(user_id=1))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_thread(self, client, auth_headers):
        resp = await client.delete("/threads/99999", headers=auth_headers(user_id=1))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_thread_forbidden_other_user(self, client, auth_headers):
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=600))
        tid = t.json()["id"]
        resp = await client.delete(f"/threads/{tid}", headers=auth_headers(user_id=999))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_like_own_thread(self, client, auth_headers):
        """Liking own thread should work (no notification to self)."""
        t = await client.post("/threads/", json={"title": "T", "description": "D"}, headers=auth_headers(user_id=700))
        tid = t.json()["id"]
        resp = await client.post(f"/likes/thread/{tid}", headers=auth_headers(user_id=700))
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "Forum Service Running"


# =====================================================================
# Auth Edge Cases
# =====================================================================
class TestAuthEdgeCases:

    @pytest.mark.asyncio
    async def test_missing_user_id_in_token(self, client):
        from jose import jwt
        token = jwt.encode(
            {"role": "member"},
            "my_very_long_super_secure_secret_key_2026_abc123",
            algorithm="HS256",
        )
        resp = await client.get("/threads/", headers={"Authorization": f"Bearer {token}"})
        # get_all_threads doesn't require auth, so this actually succeeds
        # Test on an endpoint that requires auth
        resp = await client.post(
            "/threads/",
            json={"title": "X", "description": "D"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token(self, client):
        resp = await client.post(
            "/threads/",
            json={"title": "X", "description": "D"},
            headers={"Authorization": "Bearer not.valid.jwt"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token(self, client):
        from jose import jwt
        from datetime import datetime, timezone, timedelta
        token = jwt.encode(
            {"user_id": 1, "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            "my_very_long_super_secure_secret_key_2026_abc123",
            algorithm="HS256",
        )
        resp = await client.post(
            "/threads/",
            json={"title": "X", "description": "D"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_user_missing_user_id(self, client):
        """Test get_current_auth_user with missing user_id."""
        from jose import jwt
        token = jwt.encode(
            {"role": "admin"},
            "my_very_long_super_secure_secret_key_2026_abc123",
            algorithm="HS256",
        )
        resp = await client.put(
            "/threads/1",
            json={"title": "X"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_user_expired_token(self, client):
        """Test get_current_auth_user with expired token."""
        from jose import jwt
        from datetime import datetime, timezone, timedelta
        token = jwt.encode(
            {"user_id": 1, "role": "admin", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            "my_very_long_super_secure_secret_key_2026_abc123",
            algorithm="HS256",
        )
        resp = await client.put(
            "/threads/1",
            json={"title": "X"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
