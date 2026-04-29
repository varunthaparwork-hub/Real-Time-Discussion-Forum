"""
API integration tests for forum-service endpoints.
Uses an in-memory SQLite DB and mocked auth/Redis dependencies.
Tests: threads (CRUD), comments (CRUD), likes, validation, auth.
"""
import pytest


# =====================================================================
# Thread Endpoints
# =====================================================================
class TestThreadEndpoints:

    @pytest.mark.asyncio
    async def test_create_thread(self, client, auth_headers):
        resp = await client.post(
            "/threads/",
            json={"title": "Test Thread", "description": "A description"},
            headers=auth_headers(user_id=1),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Thread"
        assert data["username"] == "user1"

    @pytest.mark.asyncio
    async def test_create_thread_unauthenticated(self, client):
        resp = await client.post(
            "/threads/",
            json={"title": "Test", "description": "Desc"},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_create_thread_sanitizes_xss(self, client, auth_headers):
        resp = await client.post(
            "/threads/",
            json={
                "title": "<script>alert('xss')</script>Clean Title",
                "description": "<div>Safe <b>bold</b></div>",
            },
            headers=auth_headers(user_id=1),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "<script>" not in data["title"]
        assert "Clean Title" in data["title"]

    @pytest.mark.asyncio
    async def test_create_thread_empty_title_rejected(self, client, auth_headers):
        resp = await client.post(
            "/threads/",
            json={"title": "", "description": "Desc"},
            headers=auth_headers(user_id=1),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_threads_paginated(self, client, auth_headers):
        # Create a few threads
        for i in range(3):
            await client.post(
                "/threads/",
                json={"title": f"Thread {i}", "description": f"Desc {i}"},
                headers=auth_headers(user_id=1),
            )
        resp = await client.get("/threads/?page=1&limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["threads"]) <= 2
        assert "total" in data
        assert "total_pages" in data

    @pytest.mark.asyncio
    async def test_get_single_thread(self, client, auth_headers):
        create_resp = await client.post(
            "/threads/",
            json={"title": "Find Me", "description": "Details"},
            headers=auth_headers(user_id=1),
        )
        thread_id = create_resp.json()["id"]
        resp = await client.get(f"/threads/{thread_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Find Me"

    @pytest.mark.asyncio
    async def test_get_nonexistent_thread_404(self, client):
        resp = await client.get("/threads/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_thread_by_owner(self, client, auth_headers):
        create_resp = await client.post(
            "/threads/",
            json={"title": "Original", "description": "Orig Desc"},
            headers=auth_headers(user_id=10),
        )
        thread_id = create_resp.json()["id"]
        resp = await client.put(
            f"/threads/{thread_id}",
            json={"title": "Updated"},
            headers=auth_headers(user_id=10),
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"

    @pytest.mark.asyncio
    async def test_update_thread_by_other_user_forbidden(self, client, auth_headers):
        create_resp = await client.post(
            "/threads/",
            json={"title": "Mine", "description": "Desc"},
            headers=auth_headers(user_id=20),
        )
        thread_id = create_resp.json()["id"]
        resp = await client.put(
            f"/threads/{thread_id}",
            json={"title": "Hacked"},
            headers=auth_headers(user_id=99),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_thread(self, client, auth_headers):
        create_resp = await client.post(
            "/threads/",
            json={"title": "Delete Me", "description": "Desc"},
            headers=auth_headers(user_id=30),
        )
        thread_id = create_resp.json()["id"]
        resp = await client.delete(
            f"/threads/{thread_id}",
            headers=auth_headers(user_id=30),
        )
        assert resp.status_code == 200

        # Verify it's gone
        get_resp = await client.get(f"/threads/{thread_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_search_threads(self, client, auth_headers):
        await client.post(
            "/threads/",
            json={"title": "Python Tutorial", "description": "Learn Python"},
            headers=auth_headers(user_id=1),
        )
        resp = await client.get("/threads/search?q=Python")
        assert resp.status_code == 200
        results = resp.json()
        assert any("Python" in t["title"] for t in results)

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty(self, client):
        resp = await client.get("/threads/search?q=")
        assert resp.status_code == 200
        assert resp.json() == []


# =====================================================================
# Comment Endpoints
# =====================================================================
class TestCommentEndpoints:

    @pytest.mark.asyncio
    async def test_create_comment(self, client, auth_headers):
        # Create a thread first
        thread_resp = await client.post(
            "/threads/",
            json={"title": "Comment Thread", "description": "Desc"},
            headers=auth_headers(user_id=1),
        )
        thread_id = thread_resp.json()["id"]

        resp = await client.post(
            "/comments/",
            json={"content": "Great post!", "thread_id": thread_id},
            headers=auth_headers(user_id=2),
        )
        assert resp.status_code == 201
        assert resp.json()["content"] == "Great post!"
        assert resp.json()["thread_id"] == thread_id

    @pytest.mark.asyncio
    async def test_create_comment_on_nonexistent_thread(self, client, auth_headers):
        resp = await client.post(
            "/comments/",
            json={"content": "Hello", "thread_id": 99999},
            headers=auth_headers(user_id=1),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_nested_reply(self, client, auth_headers):
        thread_resp = await client.post(
            "/threads/",
            json={"title": "Reply Thread", "description": "D"},
            headers=auth_headers(user_id=1),
        )
        thread_id = thread_resp.json()["id"]

        parent_resp = await client.post(
            "/comments/",
            json={"content": "Parent comment", "thread_id": thread_id},
            headers=auth_headers(user_id=2),
        )
        parent_id = parent_resp.json()["id"]

        reply_resp = await client.post(
            "/comments/",
            json={"content": "Reply", "thread_id": thread_id, "parent_id": parent_id},
            headers=auth_headers(user_id=3),
        )
        assert reply_resp.status_code == 201
        assert reply_resp.json()["parent_id"] == parent_id

    @pytest.mark.asyncio
    async def test_create_comment_sanitizes_xss(self, client, auth_headers):
        thread_resp = await client.post(
            "/threads/",
            json={"title": "XSS Thread", "description": "Desc"},
            headers=auth_headers(user_id=1),
        )
        thread_id = thread_resp.json()["id"]

        resp = await client.post(
            "/comments/",
            json={"content": "<script>steal()</script>Nice post", "thread_id": thread_id},
            headers=auth_headers(user_id=2),
        )
        assert resp.status_code == 201
        assert "<script>" not in resp.json()["content"]

    @pytest.mark.asyncio
    async def test_get_comments_by_thread(self, client, auth_headers):
        thread_resp = await client.post(
            "/threads/",
            json={"title": "List Comments", "description": "D"},
            headers=auth_headers(user_id=1),
        )
        thread_id = thread_resp.json()["id"]

        for i in range(3):
            await client.post(
                "/comments/",
                json={"content": f"Comment {i}", "thread_id": thread_id},
                headers=auth_headers(user_id=1),
            )

        resp = await client.get(f"/comments/thread/{thread_id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    @pytest.mark.asyncio
    async def test_update_comment(self, client, auth_headers):
        thread_resp = await client.post(
            "/threads/",
            json={"title": "Edit Thread", "description": "D"},
            headers=auth_headers(user_id=1),
        )
        thread_id = thread_resp.json()["id"]

        comment_resp = await client.post(
            "/comments/",
            json={"content": "Original", "thread_id": thread_id},
            headers=auth_headers(user_id=5),
        )
        comment_id = comment_resp.json()["id"]

        resp = await client.put(
            f"/comments/{comment_id}",
            json={"content": "Edited"},
            headers=auth_headers(user_id=5),
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Edited"

    @pytest.mark.asyncio
    async def test_delete_comment(self, client, auth_headers):
        thread_resp = await client.post(
            "/threads/",
            json={"title": "Del Thread", "description": "D"},
            headers=auth_headers(user_id=1),
        )
        thread_id = thread_resp.json()["id"]

        comment_resp = await client.post(
            "/comments/",
            json={"content": "Delete me", "thread_id": thread_id},
            headers=auth_headers(user_id=7),
        )
        comment_id = comment_resp.json()["id"]

        resp = await client.delete(
            f"/comments/{comment_id}",
            headers=auth_headers(user_id=7),
        )
        assert resp.status_code == 200


# =====================================================================
# Like Endpoints
# =====================================================================
class TestLikeEndpoints:

    @pytest.mark.asyncio
    async def test_like_thread(self, client, auth_headers):
        thread_resp = await client.post(
            "/threads/",
            json={"title": "Likeable", "description": "D"},
            headers=auth_headers(user_id=1),
        )
        thread_id = thread_resp.json()["id"]

        resp = await client.post(
            f"/likes/thread/{thread_id}",
            headers=auth_headers(user_id=2),
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_duplicate_like_rejected(self, client, auth_headers):
        thread_resp = await client.post(
            "/threads/",
            json={"title": "Dup Like", "description": "D"},
            headers=auth_headers(user_id=1),
        )
        thread_id = thread_resp.json()["id"]

        await client.post(f"/likes/thread/{thread_id}", headers=auth_headers(user_id=40))
        resp = await client.post(f"/likes/thread/{thread_id}", headers=auth_headers(user_id=40))
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_unlike_thread(self, client, auth_headers):
        thread_resp = await client.post(
            "/threads/",
            json={"title": "Unlike", "description": "D"},
            headers=auth_headers(user_id=1),
        )
        thread_id = thread_resp.json()["id"]

        await client.post(f"/likes/thread/{thread_id}", headers=auth_headers(user_id=50))
        resp = await client.delete(f"/likes/thread/{thread_id}", headers=auth_headers(user_id=50))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_unlike_not_liked_404(self, client, auth_headers):
        thread_resp = await client.post(
            "/threads/",
            json={"title": "Not Liked", "description": "D"},
            headers=auth_headers(user_id=1),
        )
        thread_id = thread_resp.json()["id"]
        resp = await client.delete(f"/likes/thread/{thread_id}", headers=auth_headers(user_id=60))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_thread_like_count(self, client, auth_headers):
        thread_resp = await client.post(
            "/threads/",
            json={"title": "Count Likes", "description": "D"},
            headers=auth_headers(user_id=1),
        )
        thread_id = thread_resp.json()["id"]

        await client.post(f"/likes/thread/{thread_id}", headers=auth_headers(user_id=70))
        await client.post(f"/likes/thread/{thread_id}", headers=auth_headers(user_id=71))

        resp = await client.get(f"/likes/thread/{thread_id}/count")
        assert resp.status_code == 200
        assert resp.json()["like_count"] == 2

    @pytest.mark.asyncio
    async def test_get_thread_like_status(self, client, auth_headers):
        thread_resp = await client.post(
            "/threads/",
            json={"title": "Status", "description": "D"},
            headers=auth_headers(user_id=1),
        )
        thread_id = thread_resp.json()["id"]

        resp = await client.get(f"/likes/thread/{thread_id}/status", headers=auth_headers(user_id=80))
        assert resp.json()["has_liked"] is False

        await client.post(f"/likes/thread/{thread_id}", headers=auth_headers(user_id=80))
        resp = await client.get(f"/likes/thread/{thread_id}/status", headers=auth_headers(user_id=80))
        assert resp.json()["has_liked"] is True

    @pytest.mark.asyncio
    async def test_batch_comment_like_counts(self, client, auth_headers):
        resp = await client.get("/likes/comments/counts?ids=")
        assert resp.status_code == 200
        assert resp.json()["counts"] == {}

    @pytest.mark.asyncio
    async def test_batch_comment_invalid_ids(self, client):
        resp = await client.get("/likes/comments/counts?ids=abc,def")
        assert resp.status_code == 400
