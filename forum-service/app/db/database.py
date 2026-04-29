"""
Database connection setup for the forum service.
Uses async SQLAlchemy with asyncpg driver to talk to PostgreSQL.
All other files import Base, get_db, and AsyncSessionLocal from here.
"""
from sqlalchemy.ext.asyncio import create_async_engine , AsyncSession , async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env")

# Converting postgresql:// -> postgresql+asyncpg://
DATABASE_URL = DATABASE_URL.replace("postgresql://" , "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL)

AsyncSessionLocal = async_sessionmaker(
    bind = engine, 
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit = False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
