"""
Shared test fixtures for forum-service.
Sets up an in-memory SQLite database, test HTTP client,
JWT helper, and mocks for Redis / auth-client.
"""
import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.database import Base, get_db

# ── Import all models so Base.metadata knows about every table ──────
import app.models.thread      # noqa: F401
import app.models.comment     # noqa: F401
import app.models.like        # noqa: F401
import app.models.event_outbox  # noqa: F401

# ── SQLite test database ────────────────────────────────────────────
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "test_forum.db")
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

SECRET = "my_very_long_super_secure_secret_key_2026_abc123"
ALGORITHM = "HS256"


# ── Helper: generate a valid JWT for test users ─────────────────────
def make_token(user_id: int, role: str = "member") -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


# ── DB session override ─────────────────────────────────────────────
async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


# ── Mock auth_client to avoid real HTTP / Redis calls ────────────────
async def mock_get_user_map(user_ids):
    return {
        uid: {"id": uid, "username": f"user{uid}", "avatar": None, "role": "member"}
        for uid in user_ids
    }


async def mock_get_user_role(user_id):
    return "member"


async def mock_get_users_by_usernames(usernames):
    return [
        {"id": i + 100, "username": u, "avatar": None, "role": "member"}
        for i, u in enumerate(usernames)
    ]


# ── Mock publish_event (no Redis needed) ────────────────────────────
async def mock_publish_event(event):
    pass  # silently discard events during tests


# ── App fixture ──────────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="session")
async def app():
    """Create tables once, return the patched FastAPI app."""
    # Remove stale test DB if it exists
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Patch external dependencies
    with (
        patch("app.services.auth_client.get_user_map", side_effect=mock_get_user_map),
        patch("app.services.auth_client.get_user_role", side_effect=mock_get_user_role),
        patch("app.services.auth_client.get_users_by_usernames", side_effect=mock_get_users_by_usernames),
        patch("app.services.event_publisher.publish_event", side_effect=mock_publish_event),
    ):
        from app.main import app as fastapi_app
        from app.core.rate_limiter import limiter

        # Disable rate limiting during tests
        limiter.enabled = False

        fastapi_app.dependency_overrides[get_db] = override_get_db
        yield fastapi_app
        fastapi_app.dependency_overrides.clear()
        limiter.enabled = True

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Dispose engine before cleaning up file
    await engine.dispose()

    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass  # Windows may still hold the file


@pytest_asyncio.fixture
async def client(app):
    """Async HTTP client that talks to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    """Returns a function to generate auth headers for any user."""
    def _headers(user_id: int = 1, role: str = "member"):
        token = make_token(user_id, role)
        return {"Authorization": f"Bearer {token}"}
    return _headers
