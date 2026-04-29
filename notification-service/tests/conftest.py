"""
Shared test fixtures for notification-service.
Sets up an in-memory SQLite test database, async test client, and JWT helper.
"""
import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.database import Base, get_db

# Import model so Base.metadata knows about the table
import app.models.notification  # noqa: F401

# ── In-memory SQLite test database (no file-lock issues) ────────────
TEST_DATABASE_URL = "sqlite+aiosqlite://"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

SECRET = "my_very_long_super_secure_secret_key_2026_abc123"
ALGORITHM = "HS256"


def make_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "role": "member",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


# ── App fixture ─────────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="session")
async def app():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.main import app as fastapi_app
    from app.routers.notification import limiter

    # Disable rate limiting for tests
    limiter.enabled = False

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()
    limiter.enabled = True

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    def _headers(user_id: int = 1):
        token = make_token(user_id)
        return {"Authorization": f"Bearer {token}"}
    return _headers


@pytest_asyncio.fixture
async def seed_notifications(app):
    """Insert sample notifications for user_id=1."""
    async with TestSessionLocal() as session:
        from app.models.notification import Notification

        for i in range(5):
            n = Notification(
                user_id=1,
                type="comment.created",
                title=f"Notification {i}",
                message=f"Message {i}",
                thread_id=i + 1,
                is_read=(i % 2 == 0),  # some read, some not
            )
            session.add(n)
        await session.commit()
