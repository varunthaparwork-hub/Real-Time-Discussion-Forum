"""
Notification service entry point.
On startup it launches a background task that listens to Redis
for events from the forum-service (new comments, likes, mentions)
and creates notifications + pushes them via WebSocket.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import delete

from app.routers.notification import router as notification_router
from app.routers.ws import router as ws_router
from app.services.event_consumer import start_redis_subscriber
from app.db.database import AsyncSessionLocal
from app.models.notification import Notification

logger = logging.getLogger("notification_service")

CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours
NOTIFICATION_MAX_AGE_DAYS = 30


async def _supervised_subscriber():
    """Wrapper that logs errors from subscriber but never kills the app."""
    try:
        await start_redis_subscriber()
    except asyncio.CancelledError:
        logger.info("Subscriber task cancelled")
    except Exception as exc:
        logger.error("Subscriber task died: %s", exc)


async def _cleanup_old_notifications():
    """Periodically delete notifications older than 30 days."""
    while True:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=NOTIFICATION_MAX_AGE_DAYS)
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    delete(Notification).where(Notification.created_at < cutoff)
                )
                deleted = result.rowcount
                await db.commit()
            if deleted:
                logger.info("Cleaned up %d notifications older than %d days", deleted, NOTIFICATION_MAX_AGE_DAYS)
        except asyncio.CancelledError:
            logger.info("Cleanup task cancelled")
            return
        except Exception as exc:
            logger.error("Notification cleanup failed: %s", exc)

        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    subscriber_task = asyncio.create_task(_supervised_subscriber())
    cleanup_task = asyncio.create_task(_cleanup_old_notifications())
    yield
    cleanup_task.cancel()
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Notification Service", lifespan=lifespan)

# ── Rate limiter ──────────────────────────────────────────────────────
_limiter = Limiter(key_func=get_remote_address)
app.state.limiter = _limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173", 
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notification_router)
app.include_router(ws_router)

@app.get("/")
async def health_check():
    return {"status": "Notification Service Running"}