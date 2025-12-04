"""
SQLAlchemy 데이터베이스 모델
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Student(Base):
    """학생 정보 및 상태 모델"""
    
    __tablename__ = "students"
    
    # 기본 정보
    id = Column(Integer, primary_key=True, autoincrement=True)
    zep_name = Column(String(100), unique=True, nullable=False, index=True)
    discord_id = Column(BigInteger, nullable=True, index=True)
    
    # 권한
    is_admin = Column(Boolean, default=False, index=True)
    
    # 카메라 상태
    is_cam_on = Column(Boolean, default=False, index=True)
    last_status_change = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 알림 관리
    last_alert_sent = Column(DateTime, nullable=True)
    alert_count = Column(Integer, default=0)
    
    # 학생 응답 상태
    response_status = Column(String(20), nullable=True)  # absent, camera_issue, None
    response_time = Column(DateTime, nullable=True)
    
    # 접속 종료 관련 (외출/조퇴)
    is_absent = Column(Boolean, default=False, index=True)  # 외출/조퇴 상태 여부
    absent_type = Column(String(20), nullable=True)  # "leave" (외출), "early_leave" (조퇴), None
    last_leave_time = Column(DateTime, nullable=True, index=True)  # 마지막 접속 종료 시간
    last_absent_alert = Column(DateTime, nullable=True)  # 마지막 외출/조퇴 알림 시간
    last_leave_admin_alert = Column(DateTime, nullable=True)  # 마지막 관리자 접속 종료 알림 시간
    last_return_request_time = Column(DateTime, nullable=True)  # 마지막 복귀 요청 시간
    
    # 학생 상태 관리 (지각, 외출, 조퇴, 휴가, 결석)
    status_type = Column(String(20), nullable=True, index=True)  # "late", "leave", "early_leave", "vacation", "absence", None
    status_set_at = Column(DateTime, nullable=True)  # 상태 설정 시간
    alarm_blocked_until = Column(DateTime, nullable=True, index=True)  # 알람 금지 종료 시간
    status_auto_reset_date = Column(DateTime, nullable=True)  # 자동 해제 날짜 (휴가/결석용)

    # 예약된 상태 (시간이 되면 자동으로 status_type으로 변경)
    scheduled_status_type = Column(String(20), nullable=True)  # 예약된 상태 타입
    scheduled_status_time = Column(DateTime, nullable=True, index=True)  # 예약된 상태 적용 시간
    
    # 생성/수정 시간
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return (
            f"<Student(id={self.id}, zep_name={self.zep_name}, "
            f"discord_id={self.discord_id}, is_cam_on={self.is_cam_on})>"
        )

