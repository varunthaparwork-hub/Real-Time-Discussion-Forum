"""
WebSocket authentication — verifies JWT tokens for WebSocket connections.
Unlike REST auth, this returns None instead of throwing errors,
so the WebSocket handler can close the connection gracefully
with a proper error code.
"""
import logging
import os
from dotenv import load_dotenv
from jose import JWTError, jwt

load_dotenv()

logger = logging.getLogger("ws_auth")

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def decode_ws_token(token: str) -> int | None:
    """
    Decode a JWT for WebSocket auth.
    Returns user_id on success, or None on any failure.
    The caller (ws.py) handles closing the socket with proper code.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")

        if user_id is None:
            logger.warning("WS token missing user_id claim")
            return None
        return int(user_id)

    except JWTError as exc:
        logger.warning("WS JWT decode failed: %s", exc)
        return None
    except Exception as exc:
        logger.error("Unexpected WS auth error: %s", exc)
        return None