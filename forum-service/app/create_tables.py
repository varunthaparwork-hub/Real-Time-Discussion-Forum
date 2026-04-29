# One-time script to create all forum tables in the database.
# Run this before starting the forum-service for the first time:
#   python -m app.create_tables
import asyncio

from app.db.database import Base, engine
import app.models.thread
import app.models.comment
import app.models.like
import app.models.event_outbox


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables Created Successfully")


if __name__ == "__main__":
    asyncio.run(create_tables())