"""
Event consumer using Redis Streams with consumer groups.

Uses XREADGROUP so that events are persistent and survive consumer
restarts. Unacknowledged events are automatically redelivered.
"""
import asyncio
import json
import logging
import os
from dotenv import load_dotenv
from redis.asyncio import Redis

from app.db.database import AsyncSessionLocal
from app.models.notification import Notification
from app.services.connection_manager import manager

load_dotenv()

logger = logging.getLogger("event_consumer")

REDIS_URL = os.getenv("REDIS_URL")
STREAM_NAME = "forum_events_stream"
GROUP_NAME = "notif_service_group"
CONSUMER_NAME = f"notif_worker_{os.getpid()}"

# Reconnect backoff settings
_INITIAL_DELAY = 1      # seconds
_MAX_DELAY = 30          # cap
_BACKOFF_FACTOR = 2


async def handle_event(event: dict):
    event_type = event.get("event_type")
    logger.info("Received event: type=%s", event_type)

    thread_broadcast_events = {
        "comment.created",
        "thread.liked",
        "thread.unliked",
        "comment.liked",
        "comment.unliked",
    }

    target_user_id = event.get("target_user_id")

    # Broadcast to thread room only for non-personal events (no target_user_id).
    # Personal notifications are sent directly via send_to_user below.
    if event_type in thread_broadcast_events and target_user_id is None:
        thread_id = event.get("thread_id")
        if thread_id is not None:
            await manager.send_to_thread(thread_id, event)
    if target_user_id is not None:
        try:
            async with AsyncSessionLocal() as db:
                notification = Notification(
                    user_id=target_user_id,
                    type=event_type,
                    title=event.get("title", "New Notification"),
                    message=event.get("message", ""),
                    thread_id=event.get("thread_id"),
                    comment_id=event.get("comment_id"),
                    action_user_id=event.get("action_user_id"),
                    is_read=False,
                )
                db.add(notification)
                await db.commit()
                await db.refresh(notification)

            await manager.send_to_user(target_user_id, {
                "event_type": event_type,
                "notification_id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "thread_id": notification.thread_id,
                "comment_id": notification.comment_id,
                "action_user_id": notification.action_user_id,
                "created_at": notification.created_at.isoformat(),
                "is_read": notification.is_read,
            })
            logger.info("Notification id=%s sent to user %s", notification.id, target_user_id)
        except Exception as exc:
            logger.error("Error saving/sending notification: %s", exc)


async def _ensure_consumer_group(redis: Redis) -> None:
    """Create the consumer group if it doesn't already exist."""
    try:
        await redis.xgroup_create(STREAM_NAME, GROUP_NAME, id="0", mkstream=True)
        logger.info("Created consumer group '%s' on stream '%s'", GROUP_NAME, STREAM_NAME)
    except Exception as exc:
        # BUSYGROUP = group already exists — that's fine
        if "BUSYGROUP" in str(exc):
            logger.debug("Consumer group '%s' already exists", GROUP_NAME)
        else:
            raise


async def _process_pending(redis: Redis) -> None:
    """
    Re-process any events that were delivered but not acknowledged
    (e.g., consumer crashed before calling XACK). This runs once on
    each reconnection.
    """
    logger.info("Checking for pending (unacknowledged) events ...")
    while True:
        results = await redis.xreadgroup(
            groupname=GROUP_NAME,
            consumername=CONSUMER_NAME,
            streams={STREAM_NAME: "0"},   # "0" = read my pending entries
            count=50,
        )
        if not results:
            break

        stream, messages = results[0]
        if not messages:
            break

        for msg_id, fields in messages:
            try:
                event = json.loads(fields["data"])
                await handle_event(event)
                await redis.xack(STREAM_NAME, GROUP_NAME, msg_id)
                logger.info("Reprocessed pending event %s", msg_id)
            except json.JSONDecodeError as exc:
                # Corrupt / un-parseable payload — ack to skip permanently
                logger.error("Corrupt event %s (acking to skip): %s", msg_id, exc)
                await redis.xack(STREAM_NAME, GROUP_NAME, msg_id)
            except Exception as exc:
                logger.error("Error reprocessing pending event %s: %s", msg_id, exc)
                break  # stop on error, will retry next cycle


async def start_redis_subscriber():
    """
    Consume events from a Redis Stream using consumer groups.
    Persistent — events survive consumer downtime and are replayed.
    Auto-reconnects with exponential backoff on connection loss.
    """
    delay = _INITIAL_DELAY

    while True:
        redis = None
        try:
            logger.info("Connecting to Redis stream at %s ...", REDIS_URL)
            redis = Redis.from_url(REDIS_URL, decode_responses=True)
            await redis.ping()

            # Create consumer group (idempotent)
            await _ensure_consumer_group(redis)

            # First, reprocess any events that weren't acknowledged
            await _process_pending(redis)

            logger.info("✅ Stream consumer connected, reading from '%s' (group=%s, consumer=%s)",
                         STREAM_NAME, GROUP_NAME, CONSUMER_NAME)
            delay = _INITIAL_DELAY  # reset backoff on successful connect

            # Main loop: read new events
            while True:
                results = await redis.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=CONSUMER_NAME,
                    streams={STREAM_NAME: ">"},   # ">" = only new messages
                    count=10,
                    block=5000,  # block for 5s, then loop (allows cancellation)
                )

                if not results:
                    continue  # timeout, no new messages — loop back

                stream, messages = results[0]
                for msg_id, fields in messages:
                    try:
                        event = json.loads(fields["data"])
                        await handle_event(event)
                        # Acknowledge — event won't be redelivered
                        await redis.xack(STREAM_NAME, GROUP_NAME, msg_id)
                    except json.JSONDecodeError as exc:
                        logger.error("Corrupt event %s (acking to skip): %s", msg_id, exc)
                        await redis.xack(STREAM_NAME, GROUP_NAME, msg_id)
                    except Exception as exc:
                        logger.error("Error processing event %s: %s (will be retried)", msg_id, exc)
                        # NOT acknowledged — will be redelivered on next restart

        except asyncio.CancelledError:
            logger.info("Stream consumer cancelled, shutting down")
            break
        except Exception as exc:
            logger.warning("Stream consumer lost connection: %s", exc)
        finally:
            try:
                if redis:
                    await redis.close()
            except Exception:
                pass

        logger.info("Reconnecting in %ds ...", delay)
        await asyncio.sleep(delay)
        delay = min(delay * _BACKOFF_FACTOR, _MAX_DELAY)