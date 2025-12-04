"""
CSV 파일로 학생 일괄 등록
"""
import csv
import os
from pathlib import Path
from typing import List, Tuple, Optional

from database import DBService


async def load_students_from_csv(csv_path: str = "students.csv") -> Tuple[int, int, List[str]]:
    """
    CSV 파일에서 학생 정보를 읽어 DB에 등록

    Args:
        csv_path: CSV 파일 경로 (기본값: "students.csv")

    Returns:
        (신규 등록 수, 스킵 수, 에러 목록)

    CSV 파일 형식:
        zep_name,discord_id
        홍길동,123456789012345678
        김철수,234567890123456789

    Notes:
        - 첫 줄은 헤더로 간주하고 스킵
        - discord_id가 비어있으면 None으로 처리
        - 이미 등록된 학생(zep_name 중복)은 스킵
    """
    # 파일 존재 확인
    if not os.path.exists(csv_path):
        return (0, 0, [])

    added_count = 0
    skipped_count = 0
    errors = []

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            # 필수 컬럼 확인
            if 'zep_name' not in reader.fieldnames:
                errors.append("CSV 파일에 'zep_name' 컬럼이 없습니다.")
                return (0, 0, errors)

            for row_num, row in enumerate(reader, start=2):  # 헤더 다음부터 2번째 줄
                try:
                    zep_name = row.get('zep_name', '').strip()
                    discord_id_str = row.get('discord_id', '').strip()

                    # zep_name 필수 확인
                    if not zep_name:
                        errors.append(f"줄 {row_num}: zep_name이 비어있습니다.")
                        continue

                    # discord_id 파싱 (비어있으면 None)
                    discord_id: Optional[int] = None
                    if discord_id_str:
                        try:
                            discord_id = int(discord_id_str)
                        except ValueError:
                            errors.append(f"줄 {row_num} ({zep_name}): discord_id가 숫자가 아닙니다: {discord_id_str}")
                            continue

                    # 이미 등록된 학생인지 확인 (정확 일치만)
                    existing = await DBService.get_student_by_zep_name_exact(zep_name)
                    if existing:
                        skipped_count += 1
                        continue

                    # 신규 등록
                    if discord_id:
                        await DBService.add_student(zep_name, discord_id)
                    else:
                        # discord_id 없이 등록 (나중에 웹 대시보드에서 추가)
                        await DBService.add_student_without_discord(zep_name)

                    added_count += 1

                except Exception as e:
                    errors.append(f"줄 {row_num}: 등록 실패 - {str(e)}")

    except Exception as e:
        errors.append(f"CSV 파일 읽기 실패: {str(e)}")

    return (added_count, skipped_count, errors)
