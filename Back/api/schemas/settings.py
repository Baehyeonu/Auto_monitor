"""
설정 관련 Pydantic 스키마
"""
from typing import Optional
from pydantic import BaseModel


class SettingsResponse(BaseModel):
    camera_off_threshold: int
    alert_cooldown: int
    check_interval: int
    leave_alert_threshold: int
    class_start_time: str
    class_end_time: str
    lunch_start_time: str
    lunch_end_time: str
    daily_reset_time: Optional[str]
    discord_connected: bool
    slack_connected: bool
    admin_count: int

    # 연동 토큰 설정
    discord_bot_token: Optional[str] = None
    discord_server_id: Optional[str] = None
    slack_bot_token: Optional[str] = None
    slack_app_token: Optional[str] = None
    slack_channel_id: Optional[str] = None
    google_sheets_url: Optional[str] = None
    camp_name: Optional[str] = None
    cohort_name: Optional[str] = None


class SettingsUpdate(BaseModel):
    camera_off_threshold: Optional[int] = None
    alert_cooldown: Optional[int] = None
    check_interval: Optional[int] = None
    leave_alert_threshold: Optional[int] = None
    class_start_time: Optional[str] = None
    class_end_time: Optional[str] = None
    lunch_start_time: Optional[str] = None
    lunch_end_time: Optional[str] = None
    daily_reset_time: Optional[str] = None

    # 연동 토큰 설정
    discord_bot_token: Optional[str] = None
    discord_server_id: Optional[str] = None
    slack_bot_token: Optional[str] = None
    slack_app_token: Optional[str] = None
    slack_channel_id: Optional[str] = None
    google_sheets_url: Optional[str] = None
    camp_name: Optional[str] = None
    cohort_name: Optional[str] = None

