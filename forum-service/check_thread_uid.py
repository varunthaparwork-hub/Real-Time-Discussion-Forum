import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT id, title, user_id FROM threads WHERE id = 13"))
        row = result.fetchone()
        if row:
            print(f"Thread ID: {row[0]}, Title: {row[1]}, user_id: {row[2]}, type: {type(row[2])}")
        else:
            print("Thread 13 not found")

        # Also check recent comments on thread 13
        result2 = await db.execute(text("SELECT id, user_id, thread_id, content FROM comments WHERE thread_id = 13 ORDER BY id DESC LIMIT 5"))
        rows = result2.fetchall()
        print(f"\nRecent comments on thread 13:")
        for r in rows:
            print(f"  Comment ID: {r[0]}, user_id: {r[1]}, thread_id: {r[2]}, content: {r[3][:50]}")

asyncio.run(check())
