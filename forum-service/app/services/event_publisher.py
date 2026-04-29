"""
Event publisher with Redis Streams and database outbox fallback.

Events are added to a Redis Stream (XADD) so the notification-service
consumer group can read them reliably. If Redis is down, events are
saved to a PostgreSQL outbox table and flushed when Redis recovers.
"""
import json
import logging
from app.services.redis_pool import get_redis

logger = logging.getLogger("event_publisher")

STREAM_NAME = "forum_events_stream"


async def publish_event(event: dict) -> None:
    """
    Publish to Redis Stream via XADD. If Redis is unreachable,
    save to DB outbox so the event is never lost.
    """
    try:
        redis = get_redis()
        logger.info("Publishing event type=%s to stream '%s'", event.get("event_type"), STREAM_NAME)
        msg_id = await redis.xadd(STREAM_NAME, {"data": json.dumps(event)})
        logger.info("Event published successfully (msg_id=%s)", msg_id)
    except Exception as exc:
        logger.warning("Redis publish failed (%s), saving to outbox", exc)
        await _save_to_outbox(event)


async def _save_to_outbox(event: dict) -> None:
    """Persist a failed event in the event_outbox table."""
    try:
        from app.db.database import AsyncSessionLocal
        from app.models.event_outbox import EventOutbox

        async with AsyncSessionLocal() as db:
            row = EventOutbox(
                channel=STREAM_NAME,
                payload=json.dumps(event),
            )
            db.add(row)
            await db.commit()
        logger.info("Event saved to outbox (type=%s)", event.get("event_type"))
    except Exception as exc:
        logger.error("CRITICAL: Failed to save event to outbox: %s", exc)


async def flush_outbox() -> int:
    """
    Push all pending outbox events to Redis and delete them.
    Called by a periodic background task in main.py.
    Returns the number of events flushed.
    """
    from app.db.database import AsyncSessionLocal
    from app.models.event_outbox import EventOutbox
    from sqlalchemy import select

    flushed = 0
    try:
        redis = get_redis()
        await redis.ping()  # verify Redis is alive before flushing
    except Exception:
        return 0  # Redis still down — skip this cycle

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(EventOutbox).order_by(EventOutbox.created_at).limit(100)
            )
            rows = result.scalars().all()

            for row in rows:
                try:
                    await redis.xadd(row.channel, {"data": row.payload})
                    await db.delete(row)
                    flushed += 1
                except Exception:
                    break  # Redis went down mid-flush — stop and retry later

            await db.commit()
    except Exception as exc:
        logger.error("Outbox flush error: %s", exc)

    if flushed:
        logger.info("Flushed %d events from outbox", flushed)
    return flushed