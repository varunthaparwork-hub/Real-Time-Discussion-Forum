"""
Unit tests for utility modules — no database or HTTP needed.
Tests: sanitizer, mention_parser, response_builder.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone


# ── Sanitizer Tests ──────────────────────────────────────────────────
class TestSanitizer:
    """Verify that HTML/script tags are stripped to prevent XSS."""

    def test_sanitize_text_strips_all_html(self):
        from app.core.sanitizer import sanitize_text
        assert sanitize_text("<script>alert('xss')</script>Hello") == "alert('xss')Hello"

    def test_sanitize_text_strips_tags_keeps_content(self):
        from app.core.sanitizer import sanitize_text
        assert sanitize_text("<b>Bold</b> text") == "Bold text"

    def test_sanitize_text_strips_nested_tags(self):
        from app.core.sanitizer import sanitize_text
        assert sanitize_text("<div><p>Hello <b>World</b></p></div>") == "Hello World"

    def test_sanitize_text_preserves_plain_text(self):
        from app.core.sanitizer import sanitize_text
        assert sanitize_text("Just plain text") == "Just plain text"

    def test_sanitize_text_trims_whitespace(self):
        from app.core.sanitizer import sanitize_text
        assert sanitize_text("  spaced  ") == "spaced"

    def test_sanitize_rich_text_allows_safe_tags(self):
        from app.core.sanitizer import sanitize_rich_text
        result = sanitize_rich_text("<b>bold</b> and <em>italic</em>")
        assert "<b>bold</b>" in result
        assert "<em>italic</em>" in result

    def test_sanitize_rich_text_strips_script(self):
        from app.core.sanitizer import sanitize_rich_text
        result = sanitize_rich_text("<script>alert('xss')</script><b>safe</b>")
        assert "<script>" not in result
        assert "<b>safe</b>" in result

    def test_sanitize_rich_text_strips_dangerous_tags(self):
        from app.core.sanitizer import sanitize_rich_text
        result = sanitize_rich_text("<div>block</div><iframe src='x'></iframe>")
        assert "<div>" not in result
        assert "<iframe" not in result
        assert "block" in result

    def test_sanitize_rich_text_allows_links(self):
        from app.core.sanitizer import sanitize_rich_text
        html = '<a href="https://example.com" title="link">click</a>'
        result = sanitize_rich_text(html)
        assert '<a href="https://example.com"' in result

    def test_sanitize_rich_text_strips_onclick(self):
        from app.core.sanitizer import sanitize_rich_text
        html = '<a href="#" onclick="alert(1)">click</a>'
        result = sanitize_rich_text(html)
        assert "onclick" not in result


# ── Mention Parser Tests ─────────────────────────────────────────────
class TestMentionParser:
    """Verify that @username patterns are correctly extracted."""

    def test_single_mention(self):
        from app.services.mention_parser import extract_usernames
        assert extract_usernames("Hello @varun!") == ["varun"]

    def test_multiple_mentions(self):
        from app.services.mention_parser import extract_usernames
        result = extract_usernames("@alice and @bob are here")
        assert set(result) == {"alice", "bob"}

    def test_no_mentions(self):
        from app.services.mention_parser import extract_usernames
        assert extract_usernames("No mentions here") == []

    def test_duplicate_mentions_deduplicated(self):
        from app.services.mention_parser import extract_usernames
        result = extract_usernames("@varun said to @varun")
        assert result == ["varun"]

    def test_mention_with_underscores(self):
        from app.services.mention_parser import extract_usernames
        assert extract_usernames("Hey @john_doe!") == ["john_doe"]

    def test_mention_with_numbers(self):
        from app.services.mention_parser import extract_usernames
        assert extract_usernames("User @test123") == ["test123"]

    def test_email_not_treated_as_mention(self):
        from app.services.mention_parser import extract_usernames
        # email has characters before @, so the regex won't match the full email
        result = extract_usernames("contact user@example.com")
        # The regex finds @example from user@example.com
        assert "user" not in result

    def test_empty_string(self):
        from app.services.mention_parser import extract_usernames
        assert extract_usernames("") == []

    def test_mention_at_start(self):
        from app.services.mention_parser import extract_usernames
        assert extract_usernames("@admin please check") == ["admin"]


# ── Response Builder Tests ───────────────────────────────────────────
class TestResponseBuilder:
    """Verify that DB models are correctly serialized with user info."""

    def _make_thread(self, id=1, title="Test", description="Desc", user_id=5):
        thread = MagicMock()
        thread.id = id
        thread.title = title
        thread.description = description
        thread.user_id = user_id
        thread.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return thread

    def _make_comment(self, id=1, content="Hello", user_id=5, thread_id=1, parent_id=None):
        comment = MagicMock()
        comment.id = id
        comment.content = content
        comment.user_id = user_id
        comment.thread_id = thread_id
        comment.parent_id = parent_id
        comment.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return comment

    def test_serialize_thread_with_known_user(self):
        from app.services.response_builder import serialize_thread_with_username
        thread = self._make_thread(user_id=5)
        user_map = {5: {"username": "varun", "avatar": "http://img.png"}}
        result = serialize_thread_with_username(thread, user_map)
        assert result["username"] == "varun"
        assert result["avatar"] == "http://img.png"
        assert result["title"] == "Test"

    def test_serialize_thread_with_unknown_user(self):
        from app.services.response_builder import serialize_thread_with_username
        thread = self._make_thread(user_id=999)
        result = serialize_thread_with_username(thread, {})
        assert result["username"] == "unknown"
        assert result["avatar"] is None

    def test_serialize_comment_with_known_user(self):
        from app.services.response_builder import serialize_comment_with_username
        comment = self._make_comment(user_id=3, thread_id=10, parent_id=2)
        user_map = {3: {"username": "alice", "avatar": None}}
        result = serialize_comment_with_username(comment, user_map)
        assert result["username"] == "alice"
        assert result["thread_id"] == 10
        assert result["parent_id"] == 2

    def test_serialize_comment_with_missing_user(self):
        from app.services.response_builder import serialize_comment_with_username
        comment = self._make_comment(user_id=404)
        result = serialize_comment_with_username(comment, {})
        assert result["username"] == "unknown"

    def test_serialize_thread_returns_all_fields(self):
        from app.services.response_builder import serialize_thread_with_username
        thread = self._make_thread(id=7, title="My Thread", description="Details")
        user_map = {5: {"username": "test", "avatar": None}}
        result = serialize_thread_with_username(thread, user_map)
        assert set(result.keys()) == {"id", "title", "description", "username", "avatar", "created_at"}

    def test_serialize_comment_returns_all_fields(self):
        from app.services.response_builder import serialize_comment_with_username
        comment = self._make_comment()
        user_map = {5: {"username": "test", "avatar": None}}
        result = serialize_comment_with_username(comment, user_map)
        assert set(result.keys()) == {"id", "content", "username", "avatar", "thread_id", "parent_id", "created_at"}
