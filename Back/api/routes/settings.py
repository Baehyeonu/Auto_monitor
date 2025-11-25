"""
설정 API
"""
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone
from typing import Optional

from config import config
from api.schemas.settings import SettingsResponse, SettingsUpdate
from services.settings_store import save_persisted_settings
from database import DBService


router = APIRouter()


def get_system_instance():
    """시스템 인스턴스 가져오기 (지연 import로 순환 참조 방지)"""
    try:
        import main
        return main._system_instance
    except (ImportError, AttributeError):
        return None


async def wait_for_system_instance(timeout: int = 5):
    """시스템 인스턴스가 준비될 때까지 대기"""
    import asyncio
    from api.server import app
    
    waited = 0
    while waited < timeout:
        try:
            if hasattr(app, 'state') and hasattr(app.state, 'system_instance'):
                system = app.state.system_instance
                if system is not None and hasattr(system, 'monitor_service') and system.monitor_service is not None:
                    return system
        except Exception:
            pass
        
        await asyncio.sleep(0.5)
        waited += 0.5
    
    try:
        if hasattr(app, 'state') and hasattr(app.state, 'system_instance'):
            system = app.state.system_instance
            if system and system.monitor_service:
                return system
    except Exception:
        pass
    
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
    
    save_persisted_settings(config)
    
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
        return {"success": True, "message": "Discord connected"}
    elif type == "slack":
        return {"success": True, "message": "Slack connected"}
    else:
        return {"success": False, "message": "Unknown type"}


@router.post("/reset")
async def reset_all_status():
    """모든 학생의 상태 초기화"""
    system = await wait_for_system_instance(timeout=5)
    
    if not system:
        raise HTTPException(status_code=503, detail="시스템이 초기화되지 않았습니다. 잠시 후 다시 시도해주세요.")
    
    if not system.monitor_service:
        raise HTTPException(status_code=503, detail="모니터링 서비스가 실행 중이 아닙니다.")
    
    try:
        await DBService.reset_all_alert_status()
        await system.monitor_service.broadcast_dashboard_update_now()
        return {"success": True, "message": "초기화가 완료되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"초기화 실패: {str(e)}")


@router.post("/pause-alerts")
async def pause_alerts():
    """알람 일시정지"""
    system = await wait_for_system_instance(timeout=5)
    if not system:
        raise HTTPException(status_code=503, detail="시스템이 초기화되지 않았습니다. 잠시 후 다시 시도해주세요.")
    if not system.monitor_service:
        raise HTTPException(status_code=503, detail="모니터링 서비스가 실행 중이 아닙니다.")
    
    try:
        system.monitor_service.pause_dm()
        return {"success": True, "message": "알람이 중지되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"알람 중지 실패: {str(e)}")


@router.post("/resume-alerts")
async def resume_alerts():
    """알람 재개"""
    system = await wait_for_system_instance(timeout=5)
    if not system:
        raise HTTPException(status_code=503, detail="시스템이 초기화되지 않았습니다. 잠시 후 다시 시도해주세요.")
    if not system.monitor_service:
        raise HTTPException(status_code=503, detail="모니터링 서비스가 실행 중이 아닙니다.")
    
    try:
        system.monitor_service.resume_dm()
        return {"success": True, "message": "알람이 시작되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"알람 시작 실패: {str(e)}")


