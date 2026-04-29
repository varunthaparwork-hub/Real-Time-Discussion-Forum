"""
One-time script: create performance indexes on existing tables.
Run once after the model changes. Safe to re-run (IF NOT EXISTS).
"""
import asyncio
from app.db.database import engine


INDEXES = [
    # threads
    "CREATE INDEX IF NOT EXISTS ix_threads_user_id ON threads (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_threads_created_at ON threads (created_at)",
    # comments
    "CREATE INDEX IF NOT EXISTS ix_comments_thread_id ON comments (thread_id)",
    "CREATE INDEX IF NOT EXISTS ix_comments_parent_id ON comments (parent_id)",
    "CREATE INDEX IF NOT EXISTS ix_comments_user_id ON comments (user_id)",
    # thread_likes
    "CREATE INDEX IF NOT EXISTS ix_thread_likes_thread_id ON thread_likes (thread_id)",
    "CREATE INDEX IF NOT EXISTS ix_thread_likes_user_id ON thread_likes (user_id)",
    # comment_likes
    "CREATE INDEX IF NOT EXISTS ix_comment_likes_comment_id ON comment_likes (comment_id)",
    "CREATE INDEX IF NOT EXISTS ix_comment_likes_user_id ON comment_likes (user_id)",
]


async def create_indexes():
    async with engine.begin() as conn:
        for ddl in INDEXES:
            await conn.execute(__import__("sqlalchemy").text(ddl))
            print(f"  ✔  {ddl.split(' ON ')[0].replace('CREATE INDEX IF NOT EXISTS ', '')}")
    print("\n✅ All indexes created!")


if __name__ == "__main__":
    asyncio.run(create_indexes())
