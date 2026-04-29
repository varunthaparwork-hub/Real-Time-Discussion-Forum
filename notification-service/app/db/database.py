"""
Database connection setup for the notification service.
Reads the DATABASE_URL from .env, swaps the driver to asyncpg
(so queries don't block the server), and provides a get_db()
function that hands out database sessions.
"""
from dotenv import load_dotenv
import os

from sqlalchemy.ext.asyncio import create_async_engine , AsyncSession , async_sessionmaker
from sqlalchemy.orm import declarative_base


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env")

DATABASE_URL = DATABASE_URL.replace("postgresql://" , "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL , echo=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit= False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as db:
        yield db
