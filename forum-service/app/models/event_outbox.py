"""
Event outbox table — a safety net for when Redis is down.
When forum-service can't publish an event to Redis, it saves the event
here instead. A background task checks this table every 10 seconds
and pushes any pending events to Redis once it's back up.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class EventOutbox(Base):
    __tablename__ = "event_outbox"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String, nullable=False, default="forum_events")
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
