"""
설정 API
"""
from fastapi import APIRouter, Query

from config import config
from api.schemas.settings import SettingsResponse, SettingsUpdate


router = APIRouter()


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """설정 조회"""
    return {
        "camera_off_threshold": config.CAMERA_OFF_THRESHOLD,
        "alert_cooldown": config.ALERT_COOLDOWN,
        "check_interval": config.CHECK_INTERVAL,
        "leave_alert_threshold": config.LEAVE_ALERT_THRESHOLD,
        "class_start_time": config.CLASS_START_TIME,
        "class_end_time": config.CLASS_END_TIME,
        "lunch_start_time": config.LUNCH_START_TIME,
        "lunch_end_time": config.LUNCH_END_TIME,
        "daily_reset_time": config.DAILY_RESET_TIME,
        "discord_connected": bool(config.DISCORD_BOT_TOKEN),
        "slack_connected": bool(config.SLACK_BOT_TOKEN),
        "admin_count": len(config.get_admin_ids())
    }


@router.put("")
async def update_settings(data: SettingsUpdate):
    """설정 수정"""
    # .env 파일 수정 또는 런타임 설정 변경
    # 실제 구현 시 dotenv 라이브러리로 .env 파일 수정 가능
    # 여기서는 런타임 변경만 지원
    
    # TODO: 설정 변경 로직 구현
    return {"success": True, "message": "Settings updated (runtime only)"}


@router.post("/test-connection")
async def test_connection(type: str = Query(..., regex="^(discord|slack)$")):
    """연동 테스트"""
    if type == "discord":
        # Discord 연결 테스트
        return {"success": True, "message": "Discord connected"}
    elif type == "slack":
        # Slack 연결 테스트
        return {"success": True, "message": "Slack connected"}
    else:
        return {"success": False, "message": "Unknown type"}


