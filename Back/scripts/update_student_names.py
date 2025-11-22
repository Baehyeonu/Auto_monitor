"""
기존 학생 이름을 추출된 이름으로 업데이트하는 스크립트
Slack 메시지와 동일한 로직으로 이름을 추출하여 DB를 업데이트합니다.
"""
import asyncio
import sys
import os
import re

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from database import DBService, init_db


def _extract_name_only(zep_name: str) -> str:
    """
    ZEP 이름에서 실제 이름만 추출 (다양한 구분자 지원)
    SlackListener와 동일한 로직 사용
    """
    # 다양한 구분자로 분리: /, _, -, 공백 등
    parts = re.split(r'[/_\-|\s]+', zep_name.strip())
    parts = [part.strip() for part in parts if part.strip()]
    
    # 한글이 포함된 부분 찾기
    for part in parts:
        # 한글 유니코드 범위: 가-힣
        if any('\uAC00' <= char <= '\uD7A3' for char in part):
            return part
    
    # 한글이 없으면 첫 번째 부분 반환 (기본값)
    if parts:
        return parts[0]
    
    # 빈 문자열이면 그대로 반환
    return zep_name.strip()


async def update_student_names():
    """기존 학생 이름을 추출된 이름으로 업데이트"""
    print("=" * 60)
    print("🔄 학생 이름 업데이트 스크립트")
    print("=" * 60)
    print()
    
    await init_db()
    db_service = DBService()
    
    # 모든 학생 조회
    students = await db_service.get_all_students()
    
    if not students:
        print("등록된 학생이 없습니다.")
        return
    
    print(f"📊 총 {len(students)}명의 학생을 확인합니다.\n")
    
    updated_count = 0
    unchanged_count = 0
    
    for student in students:
        original_name = student.zep_name
        extracted_name = _extract_name_only(original_name)
        
        if original_name != extracted_name:
            # 이름이 다르면 업데이트
            print(f"🔄 {original_name} → {extracted_name}")
            
            # 중복 확인
            existing = await db_service.get_student_by_zep_name(extracted_name)
            if existing and existing.id != student.id:
                print(f"   ⚠️ '{extracted_name}'은(는) 이미 다른 학생이 사용 중입니다. 건너뜁니다.")
                continue
            
            # 이름 업데이트 (직접 SQL 실행)
            from database.connection import AsyncSessionLocal
            from sqlalchemy import update
            from database.models import Student
            
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(Student)
                    .where(Student.id == student.id)
                    .values(zep_name=extracted_name)
                )
                await session.commit()
            
            print(f"   ✅ 업데이트 완료")
            updated_count += 1
        else:
            unchanged_count += 1
    
    print("\n" + "=" * 60)
    print(f"✅ 업데이트 완료")
    print(f"   • 업데이트됨: {updated_count}명")
    print(f"   • 변경 없음: {unchanged_count}명")
    print("=" * 60)


async def main():
    """메인 함수"""
    try:
        await update_student_names()
    except Exception as e:
        print(f"\n❌ 업데이트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

