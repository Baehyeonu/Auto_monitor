"""
데이터베이스 CRUD 작업
"""
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Student
from .connection import AsyncSessionLocal
from config import config


def utcnow() -> datetime:
    """UTC 기준 timezone-aware datetime"""
    return datetime.now(timezone.utc)


def to_naive(dt: datetime) -> datetime:
    """DB 저장용 naive datetime으로 변환"""
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


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
    async def get_student_by_zep_name(zep_name: str) -> Optional[Student]:
        """
        ZEP 이름으로 학생 조회
        
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
            # 상태 변경 시간 설정 (히스토리 복원 시 메시지 타임스탬프 사용)
            if status_change_time is None:
                status_change_time = utcnow()
            else:
                # 타임스탬프가 naive면 UTC로 가정
                if status_change_time.tzinfo is None:
                    status_change_time = status_change_time.replace(tzinfo=timezone.utc)
            
            # 카메라 ON 시 알림 관련 필드 초기화
            update_values = {
                "is_cam_on": is_cam_on,
                "last_status_change": to_naive(status_change_time),
                "updated_at": to_naive(utcnow())
            }
            
            if is_cam_on:
                # 카메라 켜지면 알림 기록 완전 초기화 (새 사이클로 리셋)
                update_values["last_alert_sent"] = None
                update_values["response_status"] = None
                update_values["response_time"] = None
                update_values["alert_count"] = 0
            
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
        (접속 종료한 학생은 제외 - 접속 종료 알림으로 별도 처리)
        (초기화 이후 접속한 학생만 체크 - reset_time 이후 last_status_change가 변경된 학생만)
        
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
                Student.last_leave_time.is_(None),  # 접속 종료한 학생 제외
                Student.discord_id.isnot(None)  # Discord ID가 있는 학생만
            )
            
            # 초기화 시간 이후 접속한 학생만 체크 (last_status_change > reset_time)
            if reset_time is not None:
                query = query.where(Student.last_status_change > reset_time)
            
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
            # 현재 시간에서 (ALERT_COOLDOWN - ABSENT_REMINDER_TIME) 만큼 빼서 설정
            # 이렇게 하면 ABSENT_REMINDER_TIME 후에 다시 알림이 가능해짐
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
        프로그램 시작 시 모든 학생의 알림 관련 상태 초기화
        이전 실행의 데이터로 인한 오알림 방지
        (학생 등록 정보는 유지)
        
        Returns:
            초기화 시간 (datetime)
        """
        async with AsyncSessionLocal() as session:
            now = utcnow()
            await session.execute(
                update(Student)
                .values(
                    # 카메라 상태 초기화 (재시작 시 실제 상태를 모르므로 초기화)
                    is_cam_on=False,
                    last_status_change=now,
                    # 카메라 알림 관련
                    last_alert_sent=None,
                    response_status=None,
                    response_time=None,
                    # 접속 종료 관련
                    is_absent=False,
                    absent_type=None,
                    last_leave_time=None,
                    last_absent_alert=None,
                    last_leave_admin_alert=None,
                    last_return_request_time=None,
                    updated_at=to_naive(now)
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
            
            # 초기화할 학생 ID 목록
            student_ids_to_reset = []
            
            for student in all_students:
                # timezone-naive datetime 처리
                if student.last_status_change.tzinfo is None:
                    last_change_utc = student.last_status_change.replace(tzinfo=timezone.utc)
                else:
                    last_change_utc = student.last_status_change
                
                # 초기화 시간 이전이거나 같으면 초기화 대상
                if last_change_utc <= reset_time_utc:
                    student_ids_to_reset.append(student.id)
            
            if student_ids_to_reset:
                # 초기화 대상 학생만 업데이트
                await session.execute(
                    update(Student)
                    .where(Student.id.in_(student_ids_to_reset))
                    .values(
                        # 카메라 상태 초기화
                        is_cam_on=False,
                        last_status_change=reset_time_utc,
                        # 카메라 알림 관련
                        last_alert_sent=None,
                        response_status=None,
                        response_time=None,
                        # 접속 종료 관련
                        is_absent=False,
                        absent_type=None,
                        last_leave_time=None,
                        last_absent_alert=None,
                        last_leave_admin_alert=None,
                        last_return_request_time=None,
                        updated_at=to_naive(now)
                    )
                )
                await session.commit()
                print(f"   📊 초기화 대상: {len(student_ids_to_reset)}명 (전체 {len(all_students)}명 중)")
                print(f"   💾 상태 보존: {len(all_students) - len(student_ids_to_reset)}명 (초기화 시간 이후 접속)")
            
            return reset_time_utc
    
    @staticmethod
    async def reset_camera_off_timers(reset_time: datetime):
        """
        점심 시간 시작/종료 시 카메라 OFF인 학생들의 시간 초기화
        
        Args:
            reset_time: 초기화할 시간 (점심 시작/종료 시간)
        """
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Student)
                .where(Student.is_cam_on == False)
                .values(
                    last_status_change=reset_time,
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
                .where(Student.is_absent == False)  # 외출/조퇴 상태가 아닌 학생만
                .where(Student.discord_id.isnot(None))  # Discord ID가 있는 학생만
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
            
            # 외출/조퇴 상태가 아니면 알림 안 보냄
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
            # 오늘 날짜의 끝 (내일 00:00)으로 설정하여 오늘 하루 동안 알림 안 보냄
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
            
            # 외출/조퇴 상태면 알림 안 보냄
            if student.is_absent:
                return False
            
            if student.last_leave_admin_alert is None:
                return True
            
            last_leave_admin_alert_utc = student.last_leave_admin_alert if student.last_leave_admin_alert.tzinfo else student.last_leave_admin_alert.replace(tzinfo=timezone.utc)
            elapsed = utcnow() - last_leave_admin_alert_utc
            return elapsed.total_seconds() / 60 >= cooldown_minutes
    
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
        - 오늘 접속하지 않은 학생(휴가, 결석 등)은 모니터링 대상에서 제외
        - 히스토리 복원 시 오늘 실제로 접속/종료한 학생만 상태가 업데이트됨
        - 어제 퇴근한 학생의 접속 종료 알림 방지
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
    async def reset_all_alert_fields():
        """
        모든 학생의 알림 관련 필드 초기화
        (프로그램 재시작 시 히스토리 복원 후 호출)
        
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

