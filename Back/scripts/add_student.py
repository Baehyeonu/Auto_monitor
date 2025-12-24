#!/usr/bin/env python3
"""
학생 직접 등록 스크립트
관리자가 ZEP 이름과 Discord ID를 입력하여 학생을 등록합니다.
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import DBService
from database.connection import init_db
from utils.name_utils import extract_name_only


async def add_student_manually():
    """학생 수동 등록"""
    print("=" * 50)
    print("학생 수동 등록 스크립트")
    print("=" * 50)
    print()
    
    # DB 초기화
    await init_db()
    db_service = DBService()
    
    # ZEP 이름 입력
    print("📝 ZEP 이름을 입력하세요 (예: 현우_조교)")
    zep_name = input("ZEP 이름: ").strip()
    
    if not zep_name:
        print("❌ ZEP 이름을 입력해주세요.")
        return
    
    # Discord ID 입력
    print("\n📝 Discord ID를 입력하세요")
    print("   (Discord에서 개발자 모드 활성화 → 유저 우클릭 → ID 복사)")
    discord_id_str = input("Discord ID: ").strip()
    
    if not discord_id_str:
        print("❌ Discord ID를 입력해주세요.")
        return
    
    try:
        discord_id = int(discord_id_str)
    except ValueError:
        print("❌ Discord ID는 숫자여야 합니다.")
        return
    
    # 이름 추출 (Slack 메시지와 동일한 로직)
    extracted_name = extract_name_only(zep_name)
    
    # 중복 확인 (추출된 이름으로)
    existing_zep = await db_service.get_student_by_zep_name(extracted_name)
    if existing_zep:
        print(f"\n⚠️ '{extracted_name}'은(는) 이미 등록되어 있습니다.")
        if existing_zep.discord_id:
            print(f"   Discord ID: {existing_zep.discord_id}")
        return
    
    existing_discord = await db_service.get_student_by_discord_id(discord_id)
    if existing_discord:
        print(f"\n⚠️ Discord ID {discord_id}는 이미 '{existing_discord.zep_name}'로 등록되어 있습니다.")
        return
    
    # 확인
    print("\n" + "=" * 50)
    print("등록 정보 확인")
    print("=" * 50)
    print(f"입력한 이름: {zep_name}")
    print(f"추출된 이름: {extracted_name}")
    print(f"Discord ID: {discord_id}")
    print()
    
    confirm = input("등록하시겠습니까? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("❌ 등록이 취소되었습니다.")
        return
    
    # 등록 (추출된 이름으로 저장)
    try:
        student = await db_service.add_student(extracted_name, discord_id)
        print("\n✅ 등록 완료!")
        print(f"   ZEP 이름: {student.zep_name}")
        print(f"   Discord ID: {student.discord_id}")
        print(f"   등록 시간: {student.created_at}")
    except Exception as e:
        print(f"\n❌ 등록 실패: {e}")


async def list_students():
    """등록된 학생 목록 조회"""
    print("=" * 50)
    print("등록된 학생 목록")
    print("=" * 50)
    print()
    
    await init_db()
    db_service = DBService()
    
    students = await db_service.get_all_students()
    
    if not students:
        print("등록된 학생이 없습니다.")
        return
    
    print(f"총 {len(students)}명")
    print()
    
    for i, student in enumerate(students, 1):
        print(f"{i}. {student.zep_name}")
        print(f"   Discord ID: {student.discord_id or '미등록'}")
        print(f"   카메라: {'ON' if student.is_cam_on else 'OFF'}")
        print(f"   등록일: {student.created_at}")
        print()


async def delete_student():
    """학생 삭제"""
    print("=" * 50)
    print("학생 삭제")
    print("=" * 50)
    print()
    
    await init_db()
    db_service = DBService()
    
    print("📝 삭제할 학생의 ZEP 이름을 입력하세요")
    zep_name = input("ZEP 이름: ").strip()
    
    if not zep_name:
        print("❌ ZEP 이름을 입력해주세요.")
        return
    
    # 학생 확인
    student = await db_service.get_student_by_zep_name(zep_name)
    if not student:
        print(f"❌ '{zep_name}'은(는) 등록되지 않은 학생입니다.")
        return
    
    # 확인
    print("\n" + "=" * 50)
    print("삭제할 학생 정보")
    print("=" * 50)
    print(f"ZEP 이름: {student.zep_name}")
    print(f"Discord ID: {student.discord_id or '미등록'}")
    print()
    
    confirm = input("정말 삭제하시겠습니까? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("❌ 삭제가 취소되었습니다.")
        return
    
    # 삭제
    try:
        from database.connection import AsyncSessionLocal
        from database.models import Student
        from sqlalchemy import delete
        
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(Student).where(Student.id == student.id)
            )
            await session.commit()
        
        print("\n✅ 삭제 완료!")
    except Exception as e:
        print(f"\n❌ 삭제 실패: {e}")


async def add_students_bulk():
    """전체 학생 일괄 등록"""
    print("=" * 50)
    print("전체 학생 일괄 등록")
    print("=" * 50)
    print()
    print("📝 형식: ZEP이름,DiscordID (한 줄에 하나씩)")
    print("📝 예시:")
    print("   김두한,123456789012345678")
    print("   쌍칼,987654321098765432")
    print("   개코,111222333444555666")
    print()
    print("입력을 완료하면 빈 줄을 입력하세요.")
    print()
    
    await init_db()
    db_service = DBService()
    
    students_to_add = []
    line_num = 1
    
    while True:
        line = input(f"[{line_num}] ").strip()
        
        if not line:
            # 빈 줄이면 입력 종료
            break
        
        # 쉼표로 구분
        if ',' not in line:
            print(f"   ⚠️ 형식 오류: 쉼표(,)로 구분해주세요. 건너뜁니다.")
            continue
        
        parts = line.split(',', 1)
        if len(parts) != 2:
            print(f"   ⚠️ 형식 오류: '이름,ID' 형식이 아닙니다. 건너뜁니다.")
            continue
        
        zep_name = parts[0].strip()
        discord_id_str = parts[1].strip()
        
        if not zep_name or not discord_id_str:
            print(f"   ⚠️ 이름 또는 ID가 비어있습니다. 건너뜁니다.")
            continue
        
        try:
            discord_id = int(discord_id_str)
        except ValueError:
            print(f"   ⚠️ Discord ID는 숫자여야 합니다. 건너뜁니다.")
            continue
        
        students_to_add.append((zep_name, discord_id))
        line_num += 1
    
    if not students_to_add:
        print("\n❌ 등록할 학생이 없습니다.")
        return
    
    # 등록 전 확인
    print("\n" + "=" * 50)
    print("등록할 학생 목록")
    print("=" * 50)
    for zep_name, discord_id in students_to_add:
        print(f"  • {zep_name} - {discord_id}")
    print()
    
    confirm = input(f"총 {len(students_to_add)}명을 등록하시겠습니까? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("❌ 등록이 취소되었습니다.")
        return
    
    # 일괄 등록
    success_count = 0
    fail_count = 0
    
    print("\n등록 중...")
    for zep_name, discord_id in students_to_add:
        try:
            # 이름 추출 (Slack 메시지와 동일한 로직)
            extracted_name = extract_name_only(zep_name)
            
            # 중복 확인 (추출된 이름으로)
            existing_zep = await db_service.get_student_by_zep_name(extracted_name)
            if existing_zep:
                print(f"   ⚠️ {zep_name} → {extracted_name}: 이미 등록됨 (건너뜀)")
                fail_count += 1
                continue
            
            existing_discord = await db_service.get_student_by_discord_id(discord_id)
            if existing_discord:
                print(f"   ⚠️ {zep_name} → {extracted_name}: Discord ID {discord_id} 이미 사용 중 (건너뜀)")
                fail_count += 1
                continue
            
            # 등록 (추출된 이름으로 저장)
            student = await db_service.add_student(extracted_name, discord_id)
            print(f"   ✅ {zep_name} → {extracted_name} 등록 완료")
            success_count += 1
        
        except Exception as e:
            print(f"   ❌ {zep_name} 등록 실패: {e}")
            fail_count += 1
    
    # 결과 출력
    print("\n" + "=" * 50)
    print("등록 완료")
    print("=" * 50)
    print(f"✅ 성공: {success_count}명")
    print(f"❌ 실패: {fail_count}명")
    print(f"📊 총: {len(students_to_add)}명")


async def main():
    """메인 메뉴"""
    while True:
        print("\n" + "=" * 50)
        print("ZEP 모니터링 - 학생 관리")
        print("=" * 50)
        print("1. 학생 등록 (개별)")
        print("2. 학생 일괄 등록 (전체)")
        print("3. 학생 목록 조회")
        print("4. 학생 삭제")
        print("5. 종료")
        print()
        
        choice = input("선택 (1-5): ").strip()
        
        if choice == '1':
            await add_student_manually()
        elif choice == '2':
            await add_students_bulk()
        elif choice == '3':
            await list_students()
        elif choice == '4':
            await delete_student()
        elif choice == '5':
            print("\n👋 프로그램을 종료합니다.")
            break
        else:
            print("\n❌ 잘못된 선택입니다. 1-5 중에서 선택해주세요.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 프로그램을 종료합니다.")
        sys.exit(0)
