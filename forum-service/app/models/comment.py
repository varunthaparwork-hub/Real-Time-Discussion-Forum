from sqlalchemy import Column, Integer, Text, DateTime, Index, ForeignKey
from datetime import datetime, timezone
from app.db.database import Base


def _utcnow():
    return datetime.now(timezone.utc)

"""
Comments table — replies under a thread.
Supports nested replies via parent_id (a comment can be a reply to another comment).
"""

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    user_id = Column(Integer, nullable=False)
    thread_id = Column(Integer, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)  # Nested Comments
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_comments_thread_id", "thread_id"),     # fast filter by thread
        Index("ix_comments_parent_id", "parent_id"),     # fast nested reply lookup
        Index("ix_comments_user_id", "user_id"),         # fast filter by author
    )
