"""
One-time script to create notification tables in the database.
Run this before starting the service for the first time:
  python -m app.create_tables
"""
import asyncio

from app.db.database import Base, engine
import app.models.notification


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Notification tables created successfully")


if __name__ == "__main__":
    asyncio.run(create_tables())