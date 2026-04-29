"""
Tests for WebSocket JWT authentication (ws_auth.py).
Covers: valid token, missing user_id, expired, invalid, wrong secret.
"""
import pytest
from datetime import datetime, timezone, timedelta
from jose import jwt

from app.core.ws_auth import decode_ws_token

SECRET = "my_very_long_super_secure_secret_key_2026_abc123"
ALGORITHM = "HS256"


class TestDecodeWsToken:
    def test_valid_token_returns_user_id(self):
        token = jwt.encode(
            {"user_id": 42, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            SECRET, algorithm=ALGORITHM,
        )
        assert decode_ws_token(token) == 42

    def test_missing_user_id_returns_none(self):
        token = jwt.encode(
            {"role": "member", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            SECRET, algorithm=ALGORITHM,
        )
        assert decode_ws_token(token) is None

    def test_expired_token_returns_none(self):
        token = jwt.encode(
            {"user_id": 1, "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            SECRET, algorithm=ALGORITHM,
        )
        assert decode_ws_token(token) is None

    def test_invalid_token_string_returns_none(self):
        assert decode_ws_token("not.a.valid.jwt.token") is None

    def test_wrong_secret_returns_none(self):
        token = jwt.encode(
            {"user_id": 1, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            "wrong_secret", algorithm=ALGORITHM,
        )
        assert decode_ws_token(token) is None

    def test_user_id_string_cast_to_int(self):
        token = jwt.encode(
            {"user_id": "7", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            SECRET, algorithm=ALGORITHM,
        )
        result = decode_ws_token(token)
        assert result == 7
        assert isinstance(result, int)
