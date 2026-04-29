# Likes tables — one for thread likes, one for comment likes.
# Each user can only like a given thread/comment once (unique constraint).
from sqlalchemy import Column, Integer, UniqueConstraint, ForeignKey, Index
from app.db.database import Base


class ThreadLike(Base):
    __tablename__ = 'thread_likes'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    thread_id = Column(Integer, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "thread_id", name="unique_thread_like"),
        Index("ix_thread_likes_thread_id", "thread_id"),   # fast COUNT per thread
        Index("ix_thread_likes_user_id", "user_id"),       # fast lookup per user
    )


class CommentLike(Base):
    __tablename__ = "comment_likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "comment_id", name="unique_comment_like"),
        Index("ix_comment_likes_comment_id", "comment_id"), # fast COUNT per comment
        Index("ix_comment_likes_user_id", "user_id"),       # fast lookup per user
    )