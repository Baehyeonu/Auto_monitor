"""
학생 관련 Pydantic 스키마
"""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, field_serializer


class StudentCreate(BaseModel):
    zep_name: str
    discord_id: Optional[int] = None


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
    created_at: datetime
    updated_at: datetime
    
    @field_serializer('last_status_change', 'last_alert_sent', 'last_leave_time', 'created_at', 'updated_at')
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


