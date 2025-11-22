"""
비동기 데이터베이스 연결 관리
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from config import config
from .models import Base


# 비동기 엔진 생성
engine = create_async_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite용
    poolclass=StaticPool,
    echo=False  # SQL 로그 출력 (디버깅 시 True)
)

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

