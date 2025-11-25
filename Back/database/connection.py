"""
비동기 데이터베이스 연결 관리
"""
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine import make_url
from sqlalchemy import text
from config import config
from .models import Base


database_url = config.DATABASE_URL
url = make_url(database_url)
engine_kwargs = {"echo": False}

if url.drivername.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = StaticPool
    
    if url.database:
        db_path = Path(url.database)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite+aiosqlite:///{db_path.absolute()}"
        url = make_url(database_url)
else:
    engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(database_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """데이터베이스 테이블 초기화"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        if url.drivername.startswith("sqlite"):
            result = await conn.execute(text("PRAGMA table_info(students)"))
            columns = {row[1] for row in result}
            if "is_admin" not in columns:
                await conn.execute(text("ALTER TABLE students ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
        else:
            await conn.execute(text("ALTER TABLE students ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE"))

