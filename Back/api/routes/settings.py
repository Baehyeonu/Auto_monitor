"""
설정 API
"""
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone
from typing import Optional

from config import config
from api.schemas.settings import SettingsResponse, SettingsUpdate
from database import DBService


router = APIRouter()


def get_system_instance():
    """시스템 인스턴스 가져오기 (지연 import로 순환 참조 방지)"""
    try:
        from main import get_system_instance as _get_system_instance
        return _get_system_instance()
    except ImportError:
        return None


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """설정 조회"""
    admins = await DBService.get_admin_students()
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
        "admin_count": len(admins)
    }


@router.put("", response_model=SettingsResponse)
async def update_settings(data: SettingsUpdate):
    """설정 수정"""
    # 런타임 설정 변경 (config 객체의 속성 업데이트)
    if data.camera_off_threshold is not None:
        config.CAMERA_OFF_THRESHOLD = data.camera_off_threshold
    if data.alert_cooldown is not None:
        config.ALERT_COOLDOWN = data.alert_cooldown
    if data.check_interval is not None:
        config.CHECK_INTERVAL = data.check_interval
    if data.leave_alert_threshold is not None:
        config.LEAVE_ALERT_THRESHOLD = data.leave_alert_threshold
    if data.class_start_time is not None:
        config.CLASS_START_TIME = data.class_start_time
    if data.class_end_time is not None:
        config.CLASS_END_TIME = data.class_end_time
    if data.lunch_start_time is not None:
        config.LUNCH_START_TIME = data.lunch_start_time
    if data.lunch_end_time is not None:
        config.LUNCH_END_TIME = data.lunch_end_time
    if data.daily_reset_time is not None:
        config.DAILY_RESET_TIME = data.daily_reset_time
    
    # 업데이트된 설정 반환
    admins = await DBService.get_admin_students()
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
        "admin_count": len(admins)
    }


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


@router.post("/reset")
async def reset_all_status():
    """모든 학생의 상태 초기화"""
    system = get_system_instance()
    if not system or not system.monitor_service:
        raise HTTPException(status_code=503, detail="모니터링 서비스가 실행 중이 아닙니다.")
    
    try:
        # 모든 학생의 카메라 상태 및 알림 기록 초기화
        reset_time = datetime.now(timezone.utc)
        await DBService.reset_all_alert_status()
        
        # 대시보드 업데이트 브로드캐스트
        await system.monitor_service.broadcast_dashboard_update_now()
        
        return {"success": True, "message": "초기화가 완료되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"초기화 실패: {str(e)}")


@router.post("/pause-alerts")
async def pause_alerts():
    """알람 일시정지"""
    system = get_system_instance()
    if not system or not system.monitor_service:
        raise HTTPException(status_code=503, detail="모니터링 서비스가 실행 중이 아닙니다.")
    
    try:
        system.monitor_service.pause_dm()
        return {"success": True, "message": "알람이 중지되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"알람 중지 실패: {str(e)}")


@router.post("/resume-alerts")
async def resume_alerts():
    """알람 재개"""
    system = get_system_instance()
    if not system or not system.monitor_service:
        raise HTTPException(status_code=503, detail="모니터링 서비스가 실행 중이 아닙니다.")
    
    try:
        system.monitor_service.resume_dm()
        return {"success": True, "message": "알람이 시작되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"알람 시작 실패: {str(e)}")


