"""
Notification-service API tests.
Tests: get notifications, mark single as read, mark all as read, auth.
"""
import pytest


class TestGetNotifications:
    """GET /notifications/"""

    @pytest.mark.asyncio
    async def test_get_empty_notifications(self, client, auth_headers):
        resp = await client.get(
            "/notifications/", headers=auth_headers(user_id=999)
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_notifications_with_data(self, client, auth_headers, seed_notifications):
        resp = await client.get(
            "/notifications/", headers=auth_headers(user_id=1)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        # Newest first
        assert data[0]["title"] == "Notification 4"

    @pytest.mark.asyncio
    async def test_get_notifications_unauthenticated(self, client):
        resp = await client.get("/notifications/")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_notifications_isolated_by_user(self, client, auth_headers, seed_notifications):
        """User 2 should not see user 1's notifications."""
        resp = await client.get(
            "/notifications/", headers=auth_headers(user_id=2)
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestMarkRead:
    """PATCH /notifications/{id}/read"""

    @pytest.mark.asyncio
    async def test_mark_notification_read(self, client, auth_headers, seed_notifications):
        # Get notifications for user 1
        get_resp = await client.get(
            "/notifications/", headers=auth_headers(user_id=1)
        )
        unread = [n for n in get_resp.json() if not n["is_read"]]
        assert len(unread) > 0

        notif_id = unread[0]["id"]
        resp = await client.patch(
            f"/notifications/{notif_id}/read",
            headers=auth_headers(user_id=1),
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Notification marked as read"

    @pytest.mark.asyncio
    async def test_mark_nonexistent_notification(self, client, auth_headers):
        resp = await client.patch(
            "/notifications/99999/read",
            headers=auth_headers(user_id=1),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_other_users_notification_404(self, client, auth_headers, seed_notifications):
        """User 2 should not be able to mark user 1's notifications."""
        get_resp = await client.get(
            "/notifications/", headers=auth_headers(user_id=1)
        )
        notif_id = get_resp.json()[0]["id"]

        resp = await client.patch(
            f"/notifications/{notif_id}/read",
            headers=auth_headers(user_id=2),
        )
        assert resp.status_code == 404


class TestMarkAllRead:
    """PATCH /notifications/read-all"""

    @pytest.mark.asyncio
    async def test_mark_all_read(self, client, auth_headers, seed_notifications):
        resp = await client.patch(
            "/notifications/read-all",
            headers=auth_headers(user_id=1),
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "All notifications marked as read"

        # Verify all are now read
        get_resp = await client.get(
            "/notifications/", headers=auth_headers(user_id=1)
        )
        unread = [n for n in get_resp.json() if not n["is_read"]]
        assert len(unread) == 0

    @pytest.mark.asyncio
    async def test_mark_all_read_no_notifications(self, client, auth_headers):
        """Should succeed even if user has no notifications."""
        resp = await client.patch(
            "/notifications/read-all",
            headers=auth_headers(user_id=888),
        )
        assert resp.status_code == 200
