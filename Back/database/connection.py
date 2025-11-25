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
    
    # SQLite 파일 경로 추출 및 디렉토리 생성
    # sqlite+aiosqlite:///students.db 형식에서 경로 추출
    if url.database:
        db_path = Path(url.database)
        # 절대 경로가 아니면 현재 작업 디렉토리 기준으로 처리
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        # 디렉토리가 없으면 생성
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # 데이터베이스 URL을 절대 경로로 업데이트
        database_url = f"sqlite+aiosqlite:///{db_path.absolute()}"
        url = make_url(database_url)
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

