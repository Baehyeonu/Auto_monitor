"""
Google Sheets CSV 동기화 서비스
"""
import re
import csv
import aiohttp
from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from config import config
from database import DBService
from database.db_service import now_seoul, SEOUL_TZ
import logging

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Google Sheets에서 CSV를 가져와 학생 상태를 업데이트하는 서비스"""

    def __init__(self):
        self.db_service = DBService()

    def _normalize_text(self, value: str) -> str:
        return re.sub(r"\s+", "", value).lower()

    def _normalize_cohort(self, value: str) -> str:
        normalized = self._normalize_text(value)
        return re.sub(r"(기수|기)$", "", normalized)

    def _first_non_empty(self, row: Dict[str, str], keys: List[str]) -> str:
        for key in keys:
            value = row.get(key, "").strip()
            if value:
                return value
        return ""

    def _parse_korean_time(self, time_str: str) -> Optional[str]:
        """
        한국어 시간 형식을 24시간 형식으로 변환
        예: "오전 11시 00분" -> "11:00", "오후 3시 00분" -> "15:00"
        """
        if not time_str:
            return None

        # "오전/오후 HH시 MM분" 형식 파싱
        pattern = r'(오전|오후)\s*(\d{1,2})시\s*(\d{1,2})분'
        match = re.search(pattern, time_str)

        if not match:
            return None

        period = match.group(1)  # 오전/오후
        hour = int(match.group(2))
        minute = int(match.group(3))

        # 24시간 형식으로 변환
        if period == "오후" and hour != 12:
            hour += 12
        elif period == "오전" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    def _parse_date(self, date_str: str) -> Optional[date]:
        """
        날짜 문자열 파싱
        예: "2025.12.18" 또는 "2025. 12. 18" -> date(2025, 12, 18)
        """
        if not date_str:
            return None

        try:
            # "YYYY.MM.DD" 또는 "YYYY. MM. DD" 형식 (공백 제거)
            parts = [p.strip() for p in date_str.split('.')]
            if len(parts) >= 3:
                year = int(parts[0])
                month = int(parts[1])
                day = int(parts[2])
                return date(year, month, day)
        except (ValueError, IndexError):
            pass

        return None

    def _map_status_type(self, status_kr: str) -> Optional[str]:
        """
        한국어 상태를 영어 상태 타입으로 매핑
        """
        status_mapping = {
            "지각": "late",
            "조퇴": "early_leave",
            "외출": "leave",
            "휴가": "vacation",
            "결석": "absence",
            "병원 진료 및 건강 악화": "absence"
        }
        return status_mapping.get(status_kr)

    async def fetch_csv_data(self, sheets_url: str) -> List[Dict[str, str]]:
        """
        Google Sheets에서 CSV 데이터를 가져옴

        Args:
            sheets_url: Google Sheets URL (예: https://docs.google.com/spreadsheets/d/...)

        Returns:
            CSV 행 리스트 (딕셔너리 형태)
        """
        # URL에서 spreadsheet ID와 gid 추출
        spreadsheet_id_match = re.search(r'/d/([a-zA-Z0-9-_]+)', sheets_url)
        gid_match = re.search(r'[#&]gid=(\d+)', sheets_url)

        if not spreadsheet_id_match:
            raise ValueError("Invalid Google Sheets URL")

        spreadsheet_id = spreadsheet_id_match.group(1)
        gid = gid_match.group(1) if gid_match else '0'

        # CSV export URL 생성
        csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"

        logger.info(f"[Google Sheets] CSV 다운로드 시작: {csv_url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(csv_url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch CSV: HTTP {response.status}")

                csv_text = await response.text()

        # CSV 파싱 (첫 번째 줄은 날짜 입력 안내이므로 건너뜀)
        rows = []
        lines = csv_text.splitlines()
        # 첫 번째 줄 건너뛰기
        if len(lines) > 1:
            reader = csv.DictReader(lines[1:])
            for row in reader:
                rows.append(row)

        logger.info(f"[Google Sheets] {len(rows)}개 행 로드 완료")
        return rows

    async def sync_status_from_sheets(self, sheets_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Google Sheets에서 데이터를 가져와 학생 상태를 동기화

        Args:
            sheets_url: Google Sheets URL (None이면 config에서 가져옴)

        Returns:
            동기화 결과 딕셔너리
        """
        if not sheets_url:
            sheets_url = config.GOOGLE_SHEETS_URL

        if not sheets_url:
            return {
                "success": False,
                "error": "Google Sheets URL이 설정되지 않았습니다."
            }

        try:
            # CSV 데이터 가져오기
            rows = await self.fetch_csv_data(sheets_url)

            # 통계
            processed_count = 0
            updated_count = 0
            skipped_count = 0
            error_count = 0
            errors = []
            updated_details = []  # 업데이트된 학생 상세 정보

            now_local = now_seoul()
            today = now_local.date()
            camp_filter = (config.CAMP_NAME or "").strip()
            cohort_filter = (config.COHORT_NAME or "").strip()
            camp_filter_norm = self._normalize_text(camp_filter) if camp_filter else ""
            cohort_filter_norm = self._normalize_cohort(cohort_filter) if cohort_filter else ""

            for row in rows:
                try:
                    # 필수 필드 확인
                    student_name = row.get('이름', '').strip()
                    # "지각 / 조퇴 / 외출" 컬럼이 비어있으면 "일정볼참 종류" 사용
                    status_kr = row.get('지각 / 조퇴 / 외출', '').strip() or row.get('일정볼참 종류', '').strip()
                    start_date_str = row.get('시작날짜', '').strip()

                    if not student_name or not status_kr or not start_date_str:
                        skipped_count += 1
                        continue

                    if camp_filter_norm:
                        row_camp = self._first_non_empty(row, ["캠프", "캠프명", "캠프 이름"])
                        if not row_camp or self._normalize_text(row_camp) != camp_filter_norm:
                            skipped_count += 1
                            continue

                    if cohort_filter_norm:
                        row_cohort = self._first_non_empty(row, ["기수", "기수명", "회차"])
                        if not row_cohort or self._normalize_cohort(row_cohort) != cohort_filter_norm:
                            skipped_count += 1
                            continue

                    # 상태 타입 매핑
                    status_type = self._map_status_type(status_kr)
                    if not status_type:
                        skipped_count += 1
                        logger.warning(f"[Google Sheets] 알 수 없는 상태: {status_kr}")
                        continue

                    # 날짜 파싱
                    start_date = self._parse_date(start_date_str)
                    if not start_date:
                        skipped_count += 1
                        logger.warning(f"[Google Sheets] 잘못된 날짜 형식: {start_date_str}")
                        continue

                    # 종료 날짜 (선택)
                    end_date_str = row.get('종료날짜', '').strip()
                    end_date = self._parse_date(end_date_str) if end_date_str else None

                    # 시간 파싱 (선택)
                    time_str = row.get('입실 / 퇴실 예정 시간', '').strip()
                    parsed_time = self._parse_korean_time(time_str) if time_str else None
                    time_obj = None
                    if parsed_time:
                        try:
                            time_obj = datetime.strptime(parsed_time, "%H:%M").time()
                        except ValueError:
                            skipped_count += 1
                            logger.warning(f"[Google Sheets] 잘못된 시간 형식: {parsed_time}")
                            continue

                    # 사유 (선택)
                    reason = row.get('세부 사유', '').strip() or row.get('내용', '').strip()

                    # 학생 찾기
                    student = await self.db_service.get_student_by_zep_name(student_name)
                    if not student:
                        skipped_count += 1
                        logger.warning(f"[Google Sheets] 학생을 찾을 수 없음: {student_name}")
                        continue

                    # 상태가 오늘 또는 미래인 경우만 처리
                    if start_date < today:
                        skipped_count += 1
                        continue

                    # 상태 업데이트
                    # 오늘이면 즉시 적용 또는 예약, 미래면 예약
                    is_protected = status_type in ["vacation", "absence"]
                    is_immediate = False
                    scheduled_time_str = None

                    if start_date == today:
                        if status_type == "late":
                            if time_obj:
                                scheduled_dt = datetime.combine(start_date, time_obj).replace(tzinfo=SEOUL_TZ)
                                if scheduled_dt < now_local:
                                    skipped_count += 1
                                    continue
                            is_immediate = True
                        elif status_type == "leave":
                            if time_obj:
                                scheduled_dt = datetime.combine(start_date, time_obj).replace(tzinfo=SEOUL_TZ)
                                if scheduled_dt < now_local:
                                    skipped_count += 1
                                    continue
                                scheduled_time_str = parsed_time
                            else:
                                is_immediate = True
                        elif status_type == "early_leave":
                            if time_obj:
                                scheduled_dt = datetime.combine(start_date, time_obj).replace(tzinfo=SEOUL_TZ)
                                if scheduled_dt < now_local:
                                    is_immediate = True
                                else:
                                    scheduled_time_str = parsed_time
                            else:
                                is_immediate = True
                        else:
                            # 휴가/결석은 날짜 기준으로 즉시 적용
                            is_immediate = True

                        await self.db_service.set_student_status(
                            student_id=student.id,
                            status_type=status_type,
                            status_time=scheduled_time_str if not is_immediate else None,
                            reason=reason,
                            end_date=end_date,
                            protected=is_protected
                        )
                    else:
                        # 미래 날짜 - 예약 상태로 설정
                        # scheduled_status_time에 날짜+시간을 datetime으로 저장
                        if status_type in ["vacation", "absence"]:
                            schedule_time_obj = time(0, 0)
                        else:
                            schedule_time_obj = time_obj if time_obj else time(0, 0)

                        scheduled_datetime = datetime.combine(start_date, schedule_time_obj)

                        # DB 업데이트 (scheduled_status_* 필드 사용)
                        from database.connection import AsyncSessionLocal
                        from database.models import Student
                        from sqlalchemy import update

                        async with AsyncSessionLocal() as session:
                            stmt = update(Student).where(
                                Student.id == student.id
                            ).values(
                                scheduled_status_type=status_type,
                                scheduled_status_time=scheduled_datetime,
                                status_reason=reason,
                                status_end_date=end_date,
                                status_protected=is_protected
                            )
                            await session.execute(stmt)
                            await session.commit()

                    updated_count += 1
                    processed_count += 1

                    # 상태 한글 변환
                    status_kr_display = {
                        "late": "지각",
                        "early_leave": "조퇴",
                        "leave": "외출",
                        "vacation": "휴가",
                        "absence": "결석"
                    }.get(status_type, status_type)

                    # 업데이트 상세 정보 추가
                    detail = {
                        "name": student_name,
                        "status": status_kr_display,
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d") if end_date else None,
                        "time": parsed_time,
                        "reason": reason,
                        "is_immediate": is_immediate if start_date == today else False,
                        "protected": is_protected
                    }
                    updated_details.append(detail)

                    logger.info(
                        f"[Google Sheets] {student_name}: {status_kr} "
                        f"({start_date}{f' ~ {end_date}' if end_date else ''}) "
                        f"{'즉시 적용' if (start_date == today and is_immediate) else '예약됨'}"
                    )

                except Exception as e:
                    error_count += 1
                    error_msg = f"{row.get('이름', 'Unknown')}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"[Google Sheets] 행 처리 오류: {error_msg}")

            return {
                "success": True,
                "processed": processed_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "errors": error_count,
                "error_details": errors,
                "updated_details": updated_details,
                "synced_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"[Google Sheets] 동기화 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }


# 싱글톤 인스턴스
google_sheets_service = GoogleSheetsService()
