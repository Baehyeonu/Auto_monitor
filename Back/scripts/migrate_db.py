"""
데이터베이스 마이그레이션 스크립트
접속 종료 모니터링 기능을 위한 새 컬럼 추가
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import text
from database.connection import engine


async def migrate():
    """데이터베이스 마이그레이션 실행"""
    print("=" * 60)
    print("🔄 데이터베이스 마이그레이션 시작")
    print("=" * 60)
    
    async with engine.begin() as conn:
        # 기존 컬럼 확인
        result = await conn.execute(text("PRAGMA table_info(students)"))
        columns = {row[1] for row in result.fetchall()}
        
        print(f"\n📊 기존 컬럼: {sorted(columns)}")
        
        # 추가할 컬럼 목록
        new_columns = {
            "is_absent": "BOOLEAN DEFAULT 0",
            "absent_type": "VARCHAR(20)",
            "last_leave_time": "DATETIME",
            "last_absent_alert": "DATETIME",
            "last_leave_admin_alert": "DATETIME",
            "last_return_request_time": "DATETIME"
        }
        
        added_count = 0
        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                print(f"\n➕ 컬럼 추가: {col_name} ({col_type})")
                try:
                    await conn.execute(text(f"ALTER TABLE students ADD COLUMN {col_name} {col_type}"))
                    print(f"   ✅ {col_name} 컬럼 추가 완료")
                    added_count += 1
                except Exception as e:
                    print(f"   ❌ {col_name} 컬럼 추가 실패: {e}")
            else:
                print(f"   ⏭️  {col_name} 컬럼은 이미 존재합니다 (건너뜀)")
        
        print("\n" + "=" * 60)
        if added_count > 0:
            print(f"✅ 마이그레이션 완료: {added_count}개 컬럼 추가됨")
        else:
            print("✅ 모든 컬럼이 이미 존재합니다. 마이그레이션 불필요")
        print("=" * 60)


async def main():
    """메인 함수"""
    try:
        await migrate()
    except Exception as e:
        print(f"\n❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

