"""
Forum service entry point.
This is the main FastAPI app that handles threads, comments, and likes.
On startup it also launches a background task that retries any events
that failed to publish to Redis (the outbox flusher).
"""
import asyncio
import logging
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.routers import thread, comment, like
from app.core.rate_limiter import limiter

logger = logging.getLogger("forum_service")


# Runs every 10 seconds — checks if there are any events stuck in the
# database outbox (because Redis was down) and pushes them to Redis.
async def _outbox_flusher():
    """Periodically flush failed events from the DB outbox to Redis."""
    from app.services.event_publisher import flush_outbox
    while True:
        try:
            await flush_outbox()
        except Exception as exc:
            logger.error("Outbox flusher error: %s", exc)
        await asyncio.sleep(10)  # check every 10 seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the outbox table exists
    from app.db.database import engine, Base
    import app.models.event_outbox  # noqa: F401  — register model
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    task = asyncio.create_task(_outbox_flusher())
    yield
    task.cancel()


app = FastAPI(title="Forum Service", lifespan=lifespan)

# ── Rate limiter ──────────────────────────────────────────────────────
app.state.limiter = limiter
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

app.include_router(thread.router)
app.include_router(comment.router)
app.include_router(like.router)


@app.get("/")
async def health_check():
    return {"status": "Forum Service Running"}