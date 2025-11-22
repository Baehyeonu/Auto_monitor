"""
비동기 데이터베이스 연결 관리
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine import make_url
from sqlalchemy import text
from config import config
from .models import Base


# Railway에서는 DATABASE_PRIVATE_URL이 자동으로 제공되므로 우선 사용
database_url = os.getenv("DATABASE_PRIVATE_URL") or config.DATABASE_URL
# (로컬에서 public URL을 사용해야 할 경우 DATABASE_URL에 직접 설정)
url = make_url(database_url)
engine_kwargs = {"echo": False}

if url.drivername.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = StaticPool
else:
    engine_kwargs["pool_pre_ping"] = True

# 비동기 엔진 생성
engine = create_async_engine(database_url, **engine_kwargs)

# 세션 팩토리
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

