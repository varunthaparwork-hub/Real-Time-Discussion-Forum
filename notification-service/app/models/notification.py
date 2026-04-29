"""
Notifications table — stores every notification a user receives.
For example: "@varun mentioned you in a comment" or "Someone liked your post".
Each notification is linked to the user who should see it.
"""
from datetime import datetime, timezone
from sqlalchemy import Column , Integer , String , Boolean , DateTime , Text
from app.db.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer , primary_key=True , index=True)
    user_id = Column(Integer , nullable=True , index=True)
    type = Column(String(50) , nullable=False)
    title = Column(String(255) , nullable=False)
    message = Column(Text , nullable=False)
    thread_id = Column(Integer , nullable=True)
    comment_id = Column(Integer , nullable=True)
    action_user_id = Column(Integer , nullable=True)
    is_read = Column(Boolean , default=False)
    created_at = Column(DateTime(timezone=True) , default=_utcnow)