"""
학생 관련 Pydantic 스키마
"""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, field_serializer, field_validator


class StudentCreate(BaseModel):
    zep_name: str
    discord_id: Optional[int] = None  # 타입은 int지만 문자열도 받을 수 있음
    
    @field_validator('discord_id', mode='before')
    @classmethod
    def convert_discord_id_to_int(cls, v):
        """문자열 Discord ID를 int로 변환 (JavaScript Number 정밀도 손실 방지)"""
        if v is None or v == '':
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except (ValueError, TypeError):
                return None
        return v


class StudentUpdate(BaseModel):
    zep_name: Optional[str] = None
    discord_id: Optional[int] = None


class StudentResponse(BaseModel):
    id: int
    zep_name: str
    discord_id: Optional[int]
    is_admin: bool
    is_cam_on: bool
    last_status_change: Optional[datetime]
    last_alert_sent: Optional[datetime]
    alert_count: int
    response_status: Optional[str]
    is_absent: bool
    absent_type: Optional[str]
    last_leave_time: Optional[datetime]
    status_type: Optional[str] = None
    status_set_at: Optional[datetime] = None
    alarm_blocked_until: Optional[datetime] = None
    status_auto_reset_date: Optional[datetime] = None
    status_reason: Optional[str] = None
    status_end_date: Optional[datetime] = None
    status_protected: Optional[bool] = None
    not_joined: Optional[bool] = None
    created_at: datetime
    updated_at: datetime
    
    @field_serializer('discord_id')
    def serialize_discord_id(self, value: Optional[int], _info):
        """Discord ID를 문자열로 직렬화 (JavaScript Number 정밀도 손실 방지)"""
        if value is None:
            return None
        return str(value)
    
    @field_serializer('last_status_change', 'last_alert_sent', 'last_leave_time', 'status_set_at', 'alarm_blocked_until', 'status_auto_reset_date', 'status_end_date', 'created_at', 'updated_at')
    def serialize_datetime(self, value: Optional[datetime], _info):
        """datetime을 UTC timezone을 포함한 ISO 형식으로 직렬화"""
        if value is None:
            return None
        # timezone 정보가 없으면 UTC로 간주
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        # UTC timezone을 명시적으로 포함한 ISO 형식으로 반환
        return value.isoformat()
    
    class Config:
        from_attributes = True


class AdminStatusUpdate(BaseModel):
    is_admin: bool


class StudentStatusUpdate(BaseModel):
    status_type: Optional[str] = None  # "late", "leave", "early_leave", "vacation", "absence", None (정상)
    status_time: Optional[str] = None  # 선택사항: 상태 변경 시간 "HH:MM" 형식

    @field_validator('status_type')
    @classmethod
    def validate_status_type(cls, v):
        """상태 타입 검증"""
        if v is None:
            return None
        valid_types = ["late", "leave", "early_leave", "vacation", "absence"]
        if v not in valid_types:
            raise ValueError(f"status_type must be one of {valid_types} or None")
        return v

    @field_validator('status_time')
    @classmethod
    def validate_status_time(cls, v):
        """상태 시간 검증 (HH:MM 형식)"""
        if v is None:
            return None
        from datetime import datetime
        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError("status_time must be in HH:MM format")
