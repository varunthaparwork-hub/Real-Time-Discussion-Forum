"""
Auth-service tests — registration, login, profile, role management.
Uses Django's test framework with an in-memory SQLite test database.
Throttling is disabled via force_authenticate and mocking.
"""
from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User


class TestRegistration(TestCase):
    """Register endpoint: POST /api/auth/register/"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/auth/register/"

    @patch("accounts.views.RegisterView.check_throttles")
    def test_register_success(self, _mock_throttle):
        resp = self.client.post(self.url, {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "StrongP@ss123",
            "password2": "StrongP@ss123",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    @patch("accounts.views.RegisterView.check_throttles")
    def test_register_duplicate_username(self, _mock_throttle):
        User.objects.create_user(
            username="taken", email="taken@example.com", password="StrongP@ss123"
        )
        resp = self.client.post(self.url, {
            "username": "taken",
            "email": "other@example.com",
            "password": "StrongP@ss123",
            "password2": "StrongP@ss123",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", resp.json())

    @patch("accounts.views.RegisterView.check_throttles")
    def test_register_password_mismatch(self, _mock_throttle):
        resp = self.client.post(self.url, {
            "username": "mismatch",
            "email": "mm@example.com",
            "password": "StrongP@ss123",
            "password2": "DifferentP@ss456",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.views.RegisterView.check_throttles")
    def test_register_weak_password(self, _mock_throttle):
        resp = self.client.post(self.url, {
            "username": "weakpw",
            "email": "weak@example.com",
            "password": "123",
            "password2": "123",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.views.RegisterView.check_throttles")
    def test_register_missing_fields(self, _mock_throttle):
        resp = self.client.post(self.url, {"username": "incomplete"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class TestLogin(TestCase):
    """Login endpoint: POST /api/auth/login/"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/auth/login/"
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="StrongP@ss123",
        )

    @patch("accounts.views.LoginView.check_throttles")
    def test_login_success(self, _mock_throttle):
        resp = self.client.post(self.url, {
            "username": "testuser",
            "password": "StrongP@ss123",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)

    @patch("accounts.views.LoginView.check_throttles")
    def test_login_wrong_password(self, _mock_throttle):
        resp = self.client.post(self.url, {
            "username": "testuser",
            "password": "WrongPassword",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.views.LoginView.check_throttles")
    def test_login_nonexistent_user(self, _mock_throttle):
        resp = self.client.post(self.url, {
            "username": "ghost",
            "password": "any",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.views.LoginView.check_throttles")
    def test_login_empty_body(self, _mock_throttle):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class TestProfile(TestCase):
    """Profile endpoint: GET/PUT /api/auth/profile/"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/auth/profile/"
        self.user = User.objects.create_user(
            username="profuser",
            email="prof@example.com",
            password="StrongP@ss123",
        )

    def test_get_profile_authenticated(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["username"], "profuser")

    def test_get_profile_unauthenticated(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_bio(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(self.url, {"bio": "Hello World"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, "Hello World")

    def test_update_bio_xss_sanitized(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(
            self.url,
            {"bio": "<script>alert('xss')</script>Safe text"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertNotIn("<script>", self.user.bio)
        self.assertIn("Safe text", self.user.bio)

    def test_update_avatar(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(
            self.url,
            {"avatar": "https://example.com/pic.png"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar, "https://example.com/pic.png")


class TestUserLookup(TestCase):
    """Internal user lookup endpoints (used by forum-service)."""

    def setUp(self):
        self.client = APIClient()
        self.u1 = User.objects.create_user(
            username="alice", email="alice@example.com", password="Pass1234!"
        )
        self.u2 = User.objects.create_user(
            username="bob", email="bob@example.com", password="Pass1234!"
        )

    def test_basic_lookup_by_ids(self):
        ids = f"{self.u1.id},{self.u2.id}"
        resp = self.client.get(f"/api/auth/users/basic/?ids={ids}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        usernames = [u["username"] for u in resp.json()]
        self.assertIn("alice", usernames)
        self.assertIn("bob", usernames)

    def test_basic_lookup_empty_ids(self):
        resp = self.client.get("/api/auth/users/basic/?ids=")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json(), [])

    def test_lookup_by_usernames(self):
        resp = self.client.get("/api/auth/users/by-usernames/?usernames=alice,bob")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.json()), 2)

    def test_lookup_by_usernames_nonexistent(self):
        resp = self.client.get("/api/auth/users/by-usernames/?usernames=ghost")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json(), [])


class TestRoleManagement(TestCase):
    """Admin-only role update endpoint: PUT /api/auth/users/<id>/role/"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="Admin@123"
        )
        self.admin.role = "admin"
        self.admin.save(update_fields=["role"])
        self.member = User.objects.create_user(
            username="member", email="member@example.com", password="Pass1234!"
        )

    def test_admin_can_change_role(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.put(
            f"/api/auth/users/{self.member.id}/role/",
            {"role": "moderator"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, "moderator")

    def test_non_admin_cannot_change_role(self):
        self.client.force_authenticate(user=self.member)
        resp = self.client.put(
            f"/api/auth/users/{self.member.id}/role/",
            {"role": "admin"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestSerializerSanitization(TestCase):
    """Verify bleach sanitization in serializers."""

    def test_bio_strips_html(self):
        from accounts.serializers import ProfileUpdateSerializer

        user = User.objects.create_user(
            username="sanitest", email="s@example.com", password="StrongP@ss123"
        )
        serializer = ProfileUpdateSerializer(
            user,
            data={"bio": "<b>Bold</b> <script>evil()</script> text"},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        user.refresh_from_db()
        self.assertNotIn("<script>", user.bio)
        self.assertNotIn("<b>", user.bio)
        self.assertIn("text", user.bio)

    def test_empty_bio_allowed(self):
        from accounts.serializers import ProfileUpdateSerializer

        user = User.objects.create_user(
            username="emptytest", email="e@example.com", password="StrongP@ss123"
        )
        serializer = ProfileUpdateSerializer(user, data={"bio": ""}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
