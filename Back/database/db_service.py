"""
데이터베이스 CRUD 작업
"""
import re
import logging
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Student
from .connection import AsyncSessionLocal
from config import config

# Levenshtein 거리 계산 라이브러리
try:
    from Levenshtein import distance as levenshtein_distance
    LEVENSHTEIN_AVAILABLE = True
except ImportError:
    LEVENSHTEIN_AVAILABLE = False
    logging.warning("Levenshtein 라이브러리 미설치 - 오타 허용 기능 비활성화")

logger = logging.getLogger(__name__)

# 서울 타임존 (한국 시간)
try:
    from zoneinfo import ZoneInfo
    SEOUL_TZ = ZoneInfo("Asia/Seoul")
except ImportError:
    # Python 3.8 이하 fallback
    from datetime import timezone as tz
    SEOUL_TZ = tz(timedelta(hours=9))


def utcnow() -> datetime:
    """UTC 기준 timezone-aware datetime"""
    return datetime.now(timezone.utc)


def now_seoul() -> datetime:
    """서울 타임존 기준 현재 시간 (timezone-aware)"""
    return datetime.now(SEOUL_TZ)


def to_naive(dt: datetime) -> datetime:
    """DB 저장용 naive datetime으로 변환"""
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def to_utc(local_dt: datetime) -> datetime:
    """로컬 시간을 UTC로 올바르게 변환"""
    if local_dt.tzinfo is None:
        # naive datetime은 서울 시간으로 가정
        local_dt = local_dt.replace(tzinfo=SEOUL_TZ)
    return local_dt.astimezone(timezone.utc)


def extract_name_only(zep_name: str) -> str:
    """ZEP 이름에서 실제 이름만 추출 (slack_listener와 동일 로직)"""
    if not zep_name:
        return ""

    # 구분자: /_-|공백 + .()@{}[]
    parts = re.split(r'[/_\-|\s.()@{}\[\]]+', zep_name.strip())
    parts = [part.strip() for part in parts if part.strip()]

    role_keywords = {
        "조교", "주강사", "멘토", "매니저",
        "개발자", "학생", "수강생", "교육생",
        "강사", "관리자", "운영자", "팀장",
        "강의", "실습", "프로젝트", "팀"
    }

    korean_parts = []
    for part in parts:
        if any('\uAC00' <= char <= '\uD7A3' for char in part):
            korean_parts.append(part)

    filtered = [part for part in korean_parts if part not in role_keywords]

    if filtered:
        return filtered[-1]
    elif korean_parts:
        return korean_parts[-1]

    if parts:
        return parts[0]

    return zep_name.strip()


class DBService:
    """데이터베이스 서비스 클래스"""
    
    @staticmethod
    async def add_student(zep_name: str, discord_id: int) -> Student:
        """
        새 학생 추가

        Args:
            zep_name: ZEP에서 사용하는 이름
            discord_id: Discord 유저 ID

        Returns:
            생성된 Student 객체
        """
        async with AsyncSessionLocal() as session:
            student = Student(
                zep_name=zep_name,
                discord_id=discord_id,
                is_cam_on=False,
                last_status_change=to_naive(utcnow())
            )
            session.add(student)
            await session.commit()
            await session.refresh(student)
            return student

    @staticmethod
    async def add_student_without_discord(zep_name: str) -> Student:
        """
        Discord ID 없이 학생 추가 (CSV 일괄 등록용)

        Args:
            zep_name: ZEP에서 사용하는 이름

        Returns:
            생성된 Student 객체
        """
        async with AsyncSessionLocal() as session:
            student = Student(
                zep_name=zep_name,
                discord_id=None,
                is_cam_on=False,
                last_status_change=to_naive(utcnow())
            )
            session.add(student)
            await session.commit()
            await session.refresh(student)
            return student
    
    @staticmethod
    async def get_student_by_zep_name_exact(zep_name: str) -> Optional[Student]:
        """
        ZEP 이름으로 학생 조회 (정확 일치만)

        Args:
            zep_name: ZEP 이름

        Returns:
            Student 객체 또는 None
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Student).where(Student.zep_name == zep_name)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def get_student_by_zep_name(zep_name: str) -> Optional[Student]:
        """
        ZEP 이름으로 학생 조회 (정확 일치 → 부분 일치 → 유사도 매칭)

        Args:
            zep_name: ZEP 이름

        Returns:
            Student 객체 또는 None
        """
        async with AsyncSessionLocal() as session:
            # 1. 정확 일치 시도
            result = await session.execute(
                select(Student).where(Student.zep_name == zep_name)
            )
            student = result.scalar_one_or_none()
            if student:
                return student

            # 2. 부분 일치 시도 (한글 이름 부분이 포함된 경우)
            # 예: "IH_02_김영철" -> "김영철" 추출 -> "김영철/IH02"와 매칭
            # 한글 이름 부분 추출
            korean_parts = []
            parts = re.split(r'[/_\-|\s.()@{}\[\]]+', zep_name.strip())
            for part in parts:
                if any('\uAC00' <= char <= '\uD7A3' for char in part):
                    korean_parts.append(part.strip())

            if korean_parts:
                # 한글 이름이 포함된 학생 찾기
                for korean_name in korean_parts:
                    # LIKE 검색으로 부분 일치 시도
                    result = await session.execute(
                        select(Student).where(Student.zep_name.like(f'%{korean_name}%'))
                    )
                    candidates = result.scalars().all()

                    if candidates:
                        # 정확히 일치하는 학생이 있으면 우선 반환
                        for candidate in candidates:
                            if korean_name == candidate.zep_name:
                                return candidate

                        # 정확 일치가 없으면 첫 번째 후보 반환
                        return candidates[0]

            # 3. Levenshtein 거리 기반 유사도 매칭 (오타 허용)
            if LEVENSHTEIN_AVAILABLE and korean_parts:
                # 모든 학생 조회
                result = await session.execute(select(Student))
                all_students = result.scalars().all()

                best_match = None
                best_distance = 999

                for korean_name in korean_parts:
                    for student in all_students:
                        student_name = extract_name_only(student.zep_name)
                        if not student_name:
                            continue

                        distance = levenshtein_distance(korean_name, student_name)

                        # 거리 1 이하 (1글자 차이까지 허용)
                        if distance <= 1 and distance < best_distance:
                            best_match = student
                            best_distance = distance

                if best_match:
                    logger.info(f"[유사 매칭] '{zep_name}' → '{best_match.zep_name}' (거리: {best_distance})")
                    return best_match

            return None
    
    @staticmethod
    async def get_student_by_discord_id(discord_id: int) -> Optional[Student]:
        """
        Discord ID로 학생 조회
        
        Args:
            discord_id: Discord 유저 ID
            
        Returns:
            Student 객체 또는 None
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Student).where(Student.discord_id == discord_id)
            )
            return result.scalar_one_or_none()
    
    @staticmethod
    async def get_student_by_id(student_id: int) -> Optional[Student]:
        """
        학생 ID로 학생 조회
        
        Args:
            student_id: 학생 ID
            
        Returns:
            Student 객체 또는 None
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Student).where(Student.id == student_id)
            )
            return result.scalar_one_or_none()
    
    @staticmethod
    async def update_camera_status(zep_name: str, is_cam_on: bool, status_change_time: Optional[datetime] = None) -> bool:
        """
        카메라 상태 업데이트
        
        Args:
            zep_name: ZEP 이름
            is_cam_on: 카메라 ON/OFF 상태
            status_change_time: 상태 변경 시간 (None이면 현재 시간 사용, 히스토리 복원 시 메시지 타임스탬프 사용)
            
        Returns:
            업데이트 성공 여부
        """
        async with AsyncSessionLocal() as session:
            if status_change_time is None:
                status_change_time = utcnow()
            else:
                if status_change_time.tzinfo is None:
                    status_change_time = status_change_time.replace(tzinfo=timezone.utc)
            
            update_values = {
                "is_cam_on": is_cam_on,
                "last_status_change": to_naive(status_change_time),
                "updated_at": to_naive(utcnow())
            }
            
            if is_cam_on:
                update_values["last_alert_sent"] = None
                update_values["response_status"] = None
                update_values["response_time"] = None
                update_values["alert_count"] = 0
                # 카메라가 ON이면 접속 종료 상태도 초기화 (재입장한 경우)
                update_values["last_leave_time"] = None
                
                # 지각/외출 상태인 경우 상태 변화가 있었으므로 정상으로 복귀
                # 먼저 현재 상태를 확인해야 하므로, 별도 쿼리로 처리
                result = await session.execute(
                    select(Student.status_type).where(Student.zep_name == zep_name)
                )
                current_status = result.scalar_one_or_none()
                
                if current_status in ["late", "leave"]:
                    # 지각/외출 상태를 정상으로 변경 (상태 변화가 있었으므로)
                    update_values["status_type"] = None
                    update_values["status_set_at"] = None
                    update_values["alarm_blocked_until"] = None
            
            result = await session.execute(
                update(Student)
                .where(Student.zep_name == zep_name)
                .values(**update_values)
            )
            await session.commit()
            return result.rowcount > 0
    
    @staticmethod
    async def get_students_camera_off_too_long(threshold_minutes: int, reset_time: Optional[datetime] = None) -> List[Student]:
        """
        카메라가 일정 시간 이상 꺼진 학생들 조회
        Args:
            threshold_minutes: 임계값 (분)
            reset_time: 초기화 시간 (None이면 모든 학생 체크)

        Returns:
            Student 리스트
        """
        async with AsyncSessionLocal() as session:
            threshold_time = to_naive(utcnow() - timedelta(minutes=threshold_minutes))

            query = select(Student).where(
                Student.is_cam_on == False,
                Student.last_status_change <= threshold_time,
                Student.last_leave_time.is_(None),
                Student.discord_id.isnot(None)
            )

            if reset_time is not None:
                # reset_time을 naive datetime으로 변환하여 비교
                reset_time_naive = to_naive(reset_time)
                query = query.where(Student.last_status_change > reset_time_naive)

            result = await session.execute(query)
            return result.scalars().all()
    
    @staticmethod
    async def should_send_alert(student_id: int, cooldown_minutes: int) -> bool:
        """
        알림 전송 가능 여부 확인 (쿨다운 체크)
        
        Args:
            student_id: 학생 ID
            cooldown_minutes: 쿨다운 시간 (분)
            
        Returns:
            알림 전송 가능 여부
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Student).where(Student.id == student_id)
            )
            student = result.scalar_one_or_none()
            
            if not student:
                return False
            
            if student.last_alert_sent is None:
                return True
            
            last_alert_utc = student.last_alert_sent if student.last_alert_sent.tzinfo else student.last_alert_sent.replace(tzinfo=timezone.utc)
            elapsed = utcnow() - last_alert_utc
            return elapsed.total_seconds() / 60 >= cooldown_minutes
    
    @staticmethod
    async def should_send_alert_batch(student_ids: List[int], cooldown_minutes: int) -> dict[int, bool]:
        """
        여러 학생의 알림 전송 가능 여부를 배치로 확인
        
        Args:
            student_ids: 학생 ID 리스트
            cooldown_minutes: 쿨다운 시간 (분)
            
        Returns:
            {student_id: bool} 딕셔너리
        """
        if not student_ids:
            return {}
        
        async with AsyncSessionLocal() as session:
            threshold_time = to_naive(utcnow() - timedelta(minutes=cooldown_minutes))
            
            result = await session.execute(
                select(Student.id, Student.last_alert_sent)
                .where(Student.id.in_(student_ids))
            )
            students = result.all()
            
            alert_status = {}
            for student_id in student_ids:
                alert_status[student_id] = False
            
            for student_id, last_alert_sent in students:
                if last_alert_sent is None:
                    alert_status[student_id] = True
                else:
                    last_alert_utc = last_alert_sent if last_alert_sent.tzinfo else last_alert_sent.replace(tzinfo=timezone.utc)
                    elapsed = utcnow() - last_alert_utc
                    alert_status[student_id] = elapsed.total_seconds() / 60 >= cooldown_minutes
            
            return alert_status
    
    @staticmethod
    async def record_alert_sent(student_id: int):
        """
        알림 전송 기록
        
        Args:
            student_id: 학생 ID
        """
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(
                    last_alert_sent=to_naive(utcnow()),
                    alert_count=Student.alert_count + 1,
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
    
    @staticmethod
    async def record_alerts_sent_batch(student_ids: List[int]):
        """
        여러 학생의 알림 전송을 배치로 기록
        
        Args:
            student_ids: 학생 ID 리스트
        """
        if not student_ids:
            return
        
        async with AsyncSessionLocal() as session:
            now = to_naive(utcnow())
            await session.execute(
                update(Student)
                .where(Student.id.in_(student_ids))
                .values(
                    last_alert_sent=now,
                    alert_count=Student.alert_count + 1,
                    updated_at=now
                )
            )
            await session.commit()
    
    @staticmethod
    async def record_response(student_id: int, action: str):
        """
        학생 응답 기록
        
        Args:
            student_id: 학생 ID
            action: 응답 유형 (absent)
        """
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(
                    response_status=action,
                    response_time=to_naive(utcnow()),
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
    
    @staticmethod
    async def set_absent_reminder(student_id: int):
        """
        자리 비움 선택 시 10분 후 재알림을 위한 시간 설정
        
        Args:
            student_id: 학생 ID
        """
        async with AsyncSessionLocal() as session:
            cooldown_offset = config.ALERT_COOLDOWN - config.ABSENT_REMINDER_TIME
            reminder_time = to_naive(utcnow() - timedelta(minutes=cooldown_offset))
            
            await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(
                    last_alert_sent=reminder_time,
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
    
    @staticmethod
    async def get_all_students() -> List[Student]:
        """
        모든 학생 조회
        
        Returns:
            Student 리스트
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Student))
            return result.scalars().all()
    
    @staticmethod
    async def delete_student(student_id: int) -> bool:
        """
        학생 삭제
        
        Args:
            student_id: 학생 ID
            
        Returns:
            삭제 성공 여부
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Student).where(Student.id == student_id)
            )
            student = result.scalar_one_or_none()
            if not student:
                return False
            
            await session.delete(student)
            await session.commit()
            return True
    
    @staticmethod
    async def get_camera_on_students() -> List[Student]:
        """
        현재 카메라가 켜진 학생들 조회
        
        Returns:
            카메라 ON 상태인 Student 리스트
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Student)
                .where(Student.is_cam_on == True)
                .where(Student.discord_id.isnot(None))  # Discord ID가 있는 학생만
            )
            return result.scalars().all()
    
    @staticmethod
    async def reset_all_alert_status():
        """
        프로그램 시작 시 또는 일일 초기화 시 모든 학생의 알림 관련 상태 초기화
        이전 실행의 데이터로 인한 오알림 방지
        (학생 등록 정보는 유지)

        카메라 상태와 실제 이벤트 시간은 유지하고, 알림/응답/외출/상태 관련 필드만 리셋합니다.

        Returns:
            초기화 시간 (datetime)
        """
        async with AsyncSessionLocal() as session:
            now = utcnow()
            await session.execute(
                update(Student)
                .values(
                    # 알림 관련 필드 리셋
                    last_alert_sent=None,
                    alert_count=0,
                    response_status=None,
                    response_time=None,
                    is_absent=False,
                    absent_type=None,
                    last_absent_alert=None,
                    last_leave_admin_alert=None,
                    last_return_request_time=None,
                    # 상태 관련 필드 리셋 (지각/외출/조퇴/휴가/결석)
                    status_type=None,
                    status_set_at=None,
                    alarm_blocked_until=None,
                    status_auto_reset_date=None,
                    updated_at=to_naive(now)
                    # is_cam_on, last_status_change, last_leave_time은 실제 상태이므로 유지
                )
            )
            await session.commit()
            return now
    
    @staticmethod
    async def reset_alert_status_preserving_recent(reset_time: datetime):
        """
        초기화 시간 이후 접속한 학생의 상태를 보존하면서 초기화
        (프로그램 재시작 시 이전 상태 복원용)
        
        Args:
            reset_time: 초기화 시간 (이 시간 이후 접속한 학생은 상태 유지)
        
        Returns:
            초기화 시간 (datetime)
        """
        async with AsyncSessionLocal() as session:
            now = utcnow()
            
            # reset_time을 timezone-aware로 변환
            if reset_time.tzinfo is None:
                reset_time_utc = reset_time.replace(tzinfo=timezone.utc)
            else:
                reset_time_utc = reset_time
            
            # 모든 학생 조회하여 Python에서 필터링 (timezone-naive 처리)
            result = await session.execute(select(Student))
            all_students = result.scalars().all()
            
            student_ids_to_reset = []
            
            for student in all_students:
                if student.last_status_change.tzinfo is None:
                    last_change_utc = student.last_status_change.replace(tzinfo=timezone.utc)
                else:
                    last_change_utc = student.last_status_change
                
                if last_change_utc <= reset_time_utc:
                    student_ids_to_reset.append(student.id)
            
            if student_ids_to_reset:
                await session.execute(
                    update(Student)
                    .where(Student.id.in_(student_ids_to_reset))
                    .values(
                        # 알림 관련 필드 리셋
                        last_alert_sent=None,
                        alert_count=0,
                        response_status=None,
                        response_time=None,
                        is_absent=False,
                        absent_type=None,
                        last_absent_alert=None,
                        last_leave_admin_alert=None,
                        last_return_request_time=None,
                        # 상태 관련 필드 리셋 (지각/외출/조퇴/휴가/결석)
                        status_type=None,
                        status_set_at=None,
                        alarm_blocked_until=None,
                        status_auto_reset_date=None,
                        updated_at=to_naive(now)
                        # is_cam_on, last_status_change, last_leave_time은 실제 상태이므로 유지
                    )
                )
                await session.commit()
            
            return reset_time_utc
    
    @staticmethod
    async def reset_camera_off_timers(reset_time: datetime, joined_student_ids: Optional[set] = None):
        """
        점심 시간 시작/종료 시 카메라 OFF인 학생들과 퇴장한 학생들의 시간 초기화

        Args:
            reset_time: 초기화할 시간 (점심 시작/종료 시간)
            joined_student_ids: 오늘 접속한 학생 ID 집합 (None이면 모든 카메라 OFF 학생 리셋)
        """
        async with AsyncSessionLocal() as session:
            # 카메라 OFF 학생들의 last_status_change 리셋
            camera_query = update(Student).where(Student.is_cam_on == False)

            # joined_student_ids가 제공되면 해당 학생들만 리셋
            if joined_student_ids is not None:
                if not joined_student_ids:
                    # 빈 집합이면 아무것도 리셋하지 않음
                    return
                camera_query = camera_query.where(Student.id.in_(joined_student_ids))

            await session.execute(
                camera_query.values(
                    last_status_change=to_naive(reset_time),
                    updated_at=to_naive(utcnow())
                )
            )

            # 퇴장한 학생들의 last_leave_time 리셋 (점심 시간 중 퇴장한 경우 대응)
            leave_query = update(Student).where(Student.last_leave_time.isnot(None))

            if joined_student_ids is not None:
                leave_query = leave_query.where(Student.id.in_(joined_student_ids))

            await session.execute(
                leave_query.values(
                    last_leave_time=to_naive(reset_time),
                    updated_at=to_naive(utcnow())
                )
            )

            await session.commit()
    
    @staticmethod
    async def reset_all_cameras_to_off(reset_time: datetime):
        """
        수업 종료 시 모든 학생의 카메라 상태를 OFF로 변경
        
        Args:
            reset_time: 수업 종료 시간
        """
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Student)
                .where(Student.is_cam_on == True)
                .values(
                    is_cam_on=False,
                    last_status_change=to_naive(reset_time),
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
    
    @staticmethod
    async def record_user_leave(student_id: int):
        """
        접속 종료 시간 기록
        
        Args:
            student_id: 학생 ID
        """
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(
                    last_leave_time=to_naive(utcnow()),
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
    
    @staticmethod
    async def get_students_left_too_long(threshold_minutes: int) -> List[Student]:
        """
        접속 종료 후 일정 시간 이상 복귀하지 않은 학생들 조회 (외출/조퇴 상태가 아닌 학생만)
        
        Args:
            threshold_minutes: 임계값 (분)
            
        Returns:
            Student 리스트
        """
        async with AsyncSessionLocal() as session:
            threshold_time = to_naive(utcnow() - timedelta(minutes=threshold_minutes))
            
            result = await session.execute(
                select(Student)
                .where(Student.last_leave_time.isnot(None))
                .where(Student.last_leave_time <= threshold_time)
                .where(Student.is_absent == False)
                .where(Student.discord_id.isnot(None))
            )
            return result.scalars().all()
    
    @staticmethod
    async def should_send_absent_alert(student_id: int, cooldown_minutes: int) -> bool:
        """
        외출/조퇴 알림 전송 가능 여부 확인 (쿨다운 체크)
        
        Args:
            student_id: 학생 ID
            cooldown_minutes: 쿨다운 시간 (분)
            
        Returns:
            알림 전송 가능 여부
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Student).where(Student.id == student_id)
            )
            student = result.scalar_one_or_none()
            
            if not student:
                return False
            
            if not student.is_absent:
                return False
            
            if student.last_absent_alert is None:
                return True
            
            last_absent_alert_utc = student.last_absent_alert if student.last_absent_alert.tzinfo else student.last_absent_alert.replace(tzinfo=timezone.utc)
            elapsed = utcnow() - last_absent_alert_utc
            return elapsed.total_seconds() / 60 >= cooldown_minutes
    
    @staticmethod
    async def set_absent_status(student_id: int, absent_type: str):
        """
        외출/조퇴 상태 설정 (오늘 하루 동안 알림 안 보냄)
        
        Args:
            student_id: 학생 ID
            absent_type: "leave" (외출) 또는 "early_leave" (조퇴)
        """
        async with AsyncSessionLocal() as session:
            from datetime import timedelta
            now = utcnow()
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            
            await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(
                    is_absent=True,
                    absent_type=absent_type,
                    last_absent_alert=tomorrow,  # 내일 00:00으로 설정하여 오늘 하루 알림 안 보냄
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
    
    @staticmethod
    async def clear_absent_status(student_id: int):
        """
        외출/조퇴 상태 초기화 (입장 시)
        접속 종료 관련 모든 값 초기화

        Args:
            student_id: 학생 ID
        """
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(
                    is_absent=False,
                    absent_type=None,
                    last_leave_time=None,
                    last_absent_alert=None,
                    last_leave_admin_alert=None,
                    last_return_request_time=None,
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
    
    @staticmethod
    async def record_return_request(student_id: int):
        """
        복귀 요청 시간 기록
        
        Args:
            student_id: 학생 ID
        """
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(
                    last_return_request_time=to_naive(utcnow()),
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
    
    @staticmethod
    async def get_students_with_return_request(threshold_minutes: int) -> List[Student]:
        """
        복귀 요청 후 일정 시간 이상 접속하지 않은 학생들 조회
        
        Args:
            threshold_minutes: 임계값 (분)
            
        Returns:
            Student 리스트
        """
        async with AsyncSessionLocal() as session:
            threshold_time = to_naive(utcnow() - timedelta(minutes=threshold_minutes))
            
            result = await session.execute(
                select(Student)
                .where(Student.last_return_request_time.isnot(None))
                .where(Student.last_return_request_time <= threshold_time)
                .where(Student.last_leave_time.isnot(None))  # 아직 접속 종료 상태
                .where(Student.discord_id.isnot(None))  # Discord ID가 있는 학생만
            )
            return result.scalars().all()
    
    @staticmethod
    async def record_absent_alert_sent(student_id: int):
        """
        외출/조퇴 알림 전송 기록
        
        Args:
            student_id: 학생 ID
        """
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(
                    last_absent_alert=to_naive(utcnow()),
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
    
    @staticmethod
    async def should_send_leave_admin_alert(student_id: int, cooldown_minutes: int) -> bool:
        """
        관리자 접속 종료 알림 전송 가능 여부 확인 (쿨다운 체크)
        
        Args:
            student_id: 학생 ID
            cooldown_minutes: 쿨다운 시간 (분)
            
        Returns:
            알림 전송 가능 여부
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Student).where(Student.id == student_id)
            )
            student = result.scalar_one_or_none()
            
            if not student:
                return False
            
            if student.is_absent:
                return False
            
            if student.last_leave_admin_alert is None:
                return True
            
            last_leave_admin_alert_utc = student.last_leave_admin_alert if student.last_leave_admin_alert.tzinfo else student.last_leave_admin_alert.replace(tzinfo=timezone.utc)
            elapsed = utcnow() - last_leave_admin_alert_utc
            return elapsed.total_seconds() / 60 >= cooldown_minutes
    
    @staticmethod
    async def should_send_leave_admin_alert_batch(student_ids: List[int], cooldown_minutes: int) -> dict[int, bool]:
        """
        여러 학생의 관리자 접속 종료 알림 전송 가능 여부를 배치로 확인
        
        Args:
            student_ids: 학생 ID 리스트
            cooldown_minutes: 쿨다운 시간 (분)
            
        Returns:
            {student_id: bool} 딕셔너리
        """
        if not student_ids:
            return {}
        
        async with AsyncSessionLocal() as session:
            threshold_time = to_naive(utcnow() - timedelta(minutes=cooldown_minutes))
            
            result = await session.execute(
                select(Student.id, Student.is_absent, Student.last_leave_admin_alert)
                .where(Student.id.in_(student_ids))
            )
            students = result.all()
            
            alert_status = {}
            for student_id in student_ids:
                alert_status[student_id] = False
            
            for student_id, is_absent, last_leave_admin_alert in students:
                if is_absent:
                    continue
                
                if last_leave_admin_alert is None:
                    alert_status[student_id] = True
                else:
                    last_alert_utc = last_leave_admin_alert if last_leave_admin_alert.tzinfo else last_leave_admin_alert.replace(tzinfo=timezone.utc)
                    elapsed = utcnow() - last_alert_utc
                    alert_status[student_id] = elapsed.total_seconds() / 60 >= cooldown_minutes
            
            return alert_status
    
    @staticmethod
    async def record_leave_admin_alert_sent(student_id: int):
        """
        관리자 접속 종료 알림 전송 기록
        
        Args:
            student_id: 학생 ID
        """
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(
                    last_leave_admin_alert=to_naive(utcnow()),
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
    
    @staticmethod
    async def record_leave_admin_alerts_sent_batch(student_ids: List[int]):
        """
        여러 학생의 관리자 접속 종료 알림 전송을 배치로 기록
        
        Args:
            student_ids: 학생 ID 리스트
        """
        if not student_ids:
            return
        
        async with AsyncSessionLocal() as session:
            now = to_naive(utcnow())
            await session.execute(
                update(Student)
                .where(Student.id.in_(student_ids))
                .values(
                    last_leave_admin_alert=now,
                    updated_at=now
                )
            )
            await session.commit()
    
    @staticmethod
    async def reset_all_camera_status():
        """
        모든 학생의 카메라 및 접속 상태를 초기화
        (프로그램 재시작 시 히스토리 복원 전에 호출)
        
        초기화 항목:
        - is_cam_on: False (카메라 상태)
        - last_status_change: 현재 시간
        - last_leave_time: None (접속 종료 상태)
        - is_absent: False (외출/조퇴 상태)
        - absent_type: None
        
        이유:
        """
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Student)
                .values(
                    is_cam_on=False,
                    last_status_change=to_naive(utcnow()),
                    last_leave_time=None,
                    is_absent=False,
                    absent_type=None,
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
    
    @staticmethod
    async def reset_alert_fields_partial():
        """
        백엔드 재시작 또는 동기화 시 응답 관련 필드만 초기화
        (쿨다운 타이머는 유지하여 중복 알림 방지)

        초기화 항목:
        - response_status: NULL (학생 응답 상태)
        - response_time: NULL (응답 시간)
        - last_return_request_time: NULL (복귀 요청 시간)

        유지 항목:
        - last_alert_sent (쿨다운 타이머)
        - alert_count (알림 횟수)
        - last_absent_alert (외출/조퇴 알림 쿨다운)
        - last_leave_admin_alert (접속 종료 알림 쿨다운)
        - 카메라 상태 (is_cam_on)
        - 접속 상태 (last_leave_time, is_absent)
        """
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Student)
                .values(
                    response_status=None,
                    response_time=None,
                    last_return_request_time=None,
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()

    @staticmethod
    async def reset_all_alert_fields():
        """
        일일 초기화 시 모든 알림 관련 필드 초기화

        초기화 항목:
        - last_alert_sent: NULL
        - alert_count: 0
        - response_status: NULL
        - response_time: NULL
        - last_absent_alert: NULL
        - last_leave_admin_alert: NULL
        - last_return_request_time: NULL

        유지 항목:
        - 카메라 상태 (is_cam_on)
        - 접속 상태 (last_leave_time, is_absent)
        - 학생 정보 (zep_name, discord_id)
        """
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Student)
                .values(
                    last_alert_sent=None,
                    alert_count=0,
                    response_status=None,
                    response_time=None,
                    last_absent_alert=None,
                    last_leave_admin_alert=None,
                    last_return_request_time=None,
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
    
    @staticmethod
    async def record_leave_admin_alerts_sent_batch(student_ids: List[int]):
        """
        여러 학생의 관리자 접속 종료 알림 전송을 배치로 기록
        
        Args:
            student_ids: 학생 ID 리스트
        """
        if not student_ids:
            return
        
        async with AsyncSessionLocal() as session:
            now = to_naive(utcnow())
            await session.execute(
                update(Student)
                .where(Student.id.in_(student_ids))
                .values(
                    last_leave_admin_alert=now,
                    updated_at=now
                )
            )
            await session.commit()
    
    @staticmethod
    async def get_admin_students() -> List[Student]:
        """관리자 권한을 가진 학생 목록"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Student).where(Student.is_admin == True)
            )
            return result.scalars().all()

    @staticmethod
    async def get_admin_ids() -> List[int]:
        """관리자 Discord ID 목록"""
        admins = await DBService.get_admin_students()
        return [
            student.discord_id
            for student in admins
            if student.discord_id is not None
        ]

    @staticmethod
    async def set_admin_status(student_id: int, is_admin: bool) -> bool:
        """학생의 관리자 권한 설정"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(
                    is_admin=is_admin,
                    updated_at=to_naive(utcnow())
                )
            )
            await session.commit()
            return result.rowcount > 0
    
    @staticmethod
    async def set_student_status(student_id: int, status_type: Optional[str], status_time: Optional[str] = None) -> bool:
        """
        학생 상태 설정 (지각, 외출, 조퇴, 휴가, 결석)

        Args:
            student_id: 학생 ID
            status_type: "late", "leave", "early_leave", "vacation", "absence", None (정상)
            status_time: 선택사항, 상태 변경 시간 "HH:MM" 형식 (None이면 현재 시간 사용)

        Returns:
            업데이트 성공 여부
        """
        async with AsyncSessionLocal() as session:
            now = utcnow()

            # status_time이 제공되면 해당 시간을 사용
            if status_time:
                from datetime import datetime, time as time_type
                try:
                    # HH:MM 파싱
                    time_obj = datetime.strptime(status_time, "%H:%M").time()
                    # 오늘 날짜 + 입력한 시간
                    from database.db_service import now_seoul, SEOUL_TZ
                    today_seoul = now_seoul().date()
                    custom_datetime = datetime.combine(today_seoul, time_obj)
                    # 서울 시간을 UTC로 변환
                    custom_datetime_seoul = custom_datetime.replace(tzinfo=SEOUL_TZ)
                    now = custom_datetime_seoul.astimezone(timezone.utc)
                except ValueError:
                    pass  # 파싱 실패 시 현재 시간 사용

            now_naive = to_naive(now)
            
            # 상태별 알람 금지 로직 설정
            alarm_blocked_until = None
            status_auto_reset_date = None
            
            if status_type == "late" or status_type == "leave":
                # 지각/외출: 상태 변화가 있을 때까지 알람 금지 (alarm_blocked_until은 None으로 두고, 
                # 모니터링 서비스에서 상태 변화 감지 시 해제)
                # 상태 변화 감지는 last_status_change를 모니터링하여 처리
                pass
            elif status_type == "early_leave":
                # 조퇴: 조퇴 처리 이후 알람 금지 (다음 날 자정까지)
                from datetime import date
                tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                alarm_blocked_until = to_naive(tomorrow)
            elif status_type == "vacation" or status_type == "absence":
                # 휴가/결석: 당일 알람 금지 (자정까지)
                tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                alarm_blocked_until = to_naive(tomorrow)
                status_auto_reset_date = to_naive(tomorrow)
            
            update_values = {
                "status_type": status_type,
                "status_set_at": now_naive if status_type else None,
                "alarm_blocked_until": alarm_blocked_until,
                "status_auto_reset_date": status_auto_reset_date,
                "updated_at": now_naive
            }

            # 휴가/결석 상태로 변경 시 퇴장 기록 초기화 (퇴장 목록에서 제외)
            if status_type in ["vacation", "absence"]:
                update_values["last_leave_time"] = None

            # 상태가 None이면 모든 상태 관련 필드 초기화
            if status_type is None:
                update_values.update({
                    "status_type": None,
                    "status_set_at": None,
                    "alarm_blocked_until": None,
                    "status_auto_reset_date": None
                })
            
            result = await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(**update_values)
            )
            await session.commit()
            return result.rowcount > 0
    
    @staticmethod
    async def check_and_reset_status_by_date():
        """
        날짜 기반 상태 자동 해제 (휴가/결석 등)
        매일 자정에 호출하여 status_auto_reset_date가 지난 상태를 해제
        """
        async with AsyncSessionLocal() as session:
            now = utcnow()
            now_naive = to_naive(now)
            
            # status_auto_reset_date가 현재 시간 이전인 학생들 조회
            result = await session.execute(
                select(Student)
                .where(Student.status_auto_reset_date.isnot(None))
                .where(Student.status_auto_reset_date <= now_naive)
            )
            students_to_reset = result.scalars().all()
            
            if students_to_reset:
                student_ids = [s.id for s in students_to_reset]
                await session.execute(
                    update(Student)
                    .where(Student.id.in_(student_ids))
                    .values(
                        status_type=None,
                        status_set_at=None,
                        alarm_blocked_until=None,
                        status_auto_reset_date=None,
                        updated_at=now_naive
                    )
                )
                await session.commit()
            
            return len(students_to_reset)
    
    @staticmethod
    async def is_alarm_blocked(student_id: int) -> bool:
        """
        학생의 알람이 현재 차단되어 있는지 확인
        
        Args:
            student_id: 학생 ID
            
        Returns:
            알람이 차단되어 있으면 True
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Student).where(Student.id == student_id)
            )
            student = result.scalar_one_or_none()
            
            if not student:
                return False
            
            # alarm_blocked_until이 설정되어 있고 아직 지나지 않았으면 차단
            if student.alarm_blocked_until:
                blocked_until_utc = student.alarm_blocked_until if student.alarm_blocked_until.tzinfo else student.alarm_blocked_until.replace(tzinfo=timezone.utc)
                if utcnow() < blocked_until_utc:
                    return True
            
            # 지각/외출 상태인 경우: 상태 변화가 있었는지 확인
            if student.status_type in ["late", "leave"]:
                # status_set_at 이후에 last_status_change가 변경되었으면 알람 해제
                if student.status_set_at and student.last_status_change:
                    status_set_utc = student.status_set_at if student.status_set_at.tzinfo else student.status_set_at.replace(tzinfo=timezone.utc)
                    last_change_utc = student.last_status_change if student.last_status_change.tzinfo else student.last_status_change.replace(tzinfo=timezone.utc)
                    
                    # 상태 설정 이후 상태 변화가 없으면 알람 차단
                    if last_change_utc <= status_set_utc:
                        return True
            
            return False

