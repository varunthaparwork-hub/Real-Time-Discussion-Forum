from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from datetime import datetime, timezone
from app.db.database import Base


def _utcnow():
    return datetime.now(timezone.utc)

"""
Threads table — each row is a discussion topic someone created.
Stores the title, description, who posted it, and when.
"""

class Thread(Base):
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    user_id = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_threads_user_id", "user_id"),           # fast filter by author
        Index("ix_threads_created_at", "created_at"),     # fast ORDER BY created_at
    )
