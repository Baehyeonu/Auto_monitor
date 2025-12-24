"""
환경변수 설정 관리
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


class Config(BaseSettings):
    """애플리케이션 설정"""
    
    DISCORD_BOT_TOKEN: str
    DISCORD_SERVER_ID: Optional[str] = None
    INSTRUCTOR_CHANNEL_ID: Optional[str] = None
    ADMIN_USER_IDS: str = ""
    
    SLACK_BOT_TOKEN: str
    SLACK_APP_TOKEN: str
    SLACK_CHANNEL_ID: str

    CAMERA_OFF_THRESHOLD: int = 20
    ALERT_COOLDOWN: int = 60
    CHECK_INTERVAL: int = 60
    
    CLASS_START_TIME: str = "10:10"
    CLASS_END_TIME: str = "18:40"
    LUNCH_START_TIME: str = "11:50"
    LUNCH_END_TIME: str = "12:50"
    
    ABSENT_REMINDER_TIME: int = 10
    LEAVE_ALERT_THRESHOLD: int = 30
    LEAVE_ADMIN_ALERT_COOLDOWN: int = 60
    ABSENT_ALERT_COOLDOWN: int = 30
    RETURN_REMINDER_TIME: int = 5
    
    DAILY_RESET_TIME: Optional[str] = None
    
    SCREEN_MONITOR_ENABLED: bool = False
    SCREEN_CHECK_INTERVAL: int = 1800
    FACE_DETECTION_THRESHOLD: int = 3

    GOOGLE_SHEETS_URL: Optional[str] = None
    CAMP_NAME: Optional[str] = None
    COHORT_NAME: Optional[str] = None

    DATABASE_URL: str = "sqlite+aiosqlite:///students.db"
    
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_prefix="",
        extra="ignore",
    )
    
    def get_admin_ids(self) -> List[int]:
        if not self.ADMIN_USER_IDS:
            return []
        
        try:
            ids = [int(id.strip()) for id in self.ADMIN_USER_IDS.split(",") if id.strip()]
            return ids
        except ValueError:
            return []


import os

required_vars = ["DISCORD_BOT_TOKEN", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_CHANNEL_ID"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    raise ValueError(f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing_vars)}")

config = Config()

try:
    from services.settings_store import load_persisted_settings

    load_persisted_settings(config)
except Exception as e:
    print(f"[Config] persisted settings load failed: {e}")
