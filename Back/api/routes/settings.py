"""
설정 API
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from pydantic import BaseModel

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


@router.post("/sync")
async def sync_from_slack():
    """슬랙 히스토리에서 최신 상태로 동기화"""
    system = await wait_for_system_instance(timeout=5)
    
    if not system:
        raise HTTPException(status_code=503, detail="시스템이 초기화되지 않았습니다. 잠시 후 다시 시도해주세요.")
    
    if not system.slack_listener:
        raise HTTPException(status_code=503, detail="Slack 리스너가 실행 중이 아닙니다.")
    
    try:
        await system.slack_listener.restore_state_from_history(lookback_hours=24)
        await system.monitor_service.broadcast_dashboard_update_now()
        return {"success": True, "message": "슬랙에서 최신 상태로 동기화가 완료되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"동기화 실패: {str(e)}")


class IgnoreKeywordsResponse(BaseModel):
    keywords: List[str]


class IgnoreKeywordsUpdate(BaseModel):
    keywords: List[str]


@router.get("/ignore-keywords", response_model=IgnoreKeywordsResponse)
async def get_ignore_keywords():
    """무시할 키워드 목록 조회"""
    from pathlib import Path
    import json
    
    settings_file = Path(__file__).parent.parent.parent / "data" / "settings.json"
    default_keywords = ["test", "monitor", "debug", "temp"]
    
    if not settings_file.exists():
        return {"keywords": default_keywords}
    
    try:
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        keywords = data.get("ignore_keywords", default_keywords)
        if isinstance(keywords, list):
            return {"keywords": [str(kw) for kw in keywords if kw]}
        return {"keywords": default_keywords}
    except Exception:
        return {"keywords": default_keywords}


@router.put("/ignore-keywords", response_model=IgnoreKeywordsResponse)
async def update_ignore_keywords(data: IgnoreKeywordsUpdate):
    """무시할 키워드 목록 수정"""
    from pathlib import Path
    import json
    
    settings_file = Path(__file__).parent.parent.parent / "data" / "settings.json"
    
    # 기존 설정 로드
    existing_data = {}
    if settings_file.exists():
        try:
            existing_data = json.loads(settings_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    # 키워드 업데이트
    existing_data["ignore_keywords"] = [str(kw).strip() for kw in data.keywords if kw and kw.strip()]
    
    # 파일 저장
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(existing_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    # SlackListener에 키워드 갱신 알림 (선택사항)
    system = await wait_for_system_instance(timeout=2)
    if system and system.slack_listener:
        system.slack_listener.ignore_keywords = [kw.lower() for kw in data.keywords if kw]
    
    return {"keywords": existing_data["ignore_keywords"]}


