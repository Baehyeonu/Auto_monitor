"""
학생 관련 Pydantic 스키마
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


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
    
    class Config:
        from_attributes = True


