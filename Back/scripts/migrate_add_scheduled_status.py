"""
DB 마이그레이션: scheduled_status_type, scheduled_status_time 필드 추가
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from database.connection import AsyncSessionLocal


async def migrate():
    """scheduled_status 관련 컬럼 추가"""
    async with AsyncSessionLocal() as session:
        print("🔧 DB 마이그레이션 시작...")

        try:
            # scheduled_status_type 컬럼 추가
            await session.execute(text("""
                ALTER TABLE students
                ADD COLUMN scheduled_status_type VARCHAR(20)
            """))
            print("✅ scheduled_status_type 컬럼 추가 완료")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️  scheduled_status_type 컬럼이 이미 존재합니다")
            else:
                print(f"❌ scheduled_status_type 컬럼 추가 실패: {e}")

        try:
            # scheduled_status_time 컬럼 추가
            await session.execute(text("""
                ALTER TABLE students
                ADD COLUMN scheduled_status_time DATETIME
            """))
            print("✅ scheduled_status_time 컬럼 추가 완료")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️  scheduled_status_time 컬럼이 이미 존재합니다")
            else:
                print(f"❌ scheduled_status_time 컬럼 추가 실패: {e}")

        try:
            # scheduled_status_time에 인덱스 추가
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_students_scheduled_status_time
                ON students (scheduled_status_time)
            """))
            print("✅ scheduled_status_time 인덱스 추가 완료")
        except Exception as e:
            print(f"❌ scheduled_status_time 인덱스 추가 실패: {e}")

        await session.commit()
        print("✅ DB 마이그레이션 완료!")


if __name__ == "__main__":
    asyncio.run(migrate())
