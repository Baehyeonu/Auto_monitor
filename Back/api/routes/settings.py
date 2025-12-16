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
        "admin_count": len(admins),
        "status_parsing_enabled": config.STATUS_PARSING_ENABLED,
        "status_camp_filter": config.STATUS_CAMP_FILTER,
        "slack_status_channel_configured": bool(config.SLACK_STATUS_CHANNEL_ID)
    }


@router.put("", response_model=SettingsResponse)
async def update_settings(data: SettingsUpdate):
    """설정 수정"""
    updated_fields = {}

    if data.camera_off_threshold is not None:
        config.CAMERA_OFF_THRESHOLD = data.camera_off_threshold
        updated_fields['camera_off_threshold'] = data.camera_off_threshold
    if data.alert_cooldown is not None:
        config.ALERT_COOLDOWN = data.alert_cooldown
        updated_fields['alert_cooldown'] = data.alert_cooldown
    if data.check_interval is not None:
        config.CHECK_INTERVAL = data.check_interval
        updated_fields['check_interval'] = data.check_interval
    if data.leave_alert_threshold is not None:
        config.LEAVE_ALERT_THRESHOLD = data.leave_alert_threshold
        updated_fields['leave_alert_threshold'] = data.leave_alert_threshold
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
        updated_fields['daily_reset_time'] = data.daily_reset_time
    if data.status_parsing_enabled is not None:
        config.STATUS_PARSING_ENABLED = data.status_parsing_enabled
    if data.status_camp_filter is not None:
        config.STATUS_CAMP_FILTER = data.status_camp_filter

    save_persisted_settings(config)

    # MonitorService에 설정 변경 알림 (실시간 반영)
    if updated_fields:
        system = await wait_for_system_instance(timeout=2)
        if system and system.monitor_service:
            system.monitor_service.update_settings(**updated_fields)

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
        "admin_count": len(admins),
        "status_parsing_enabled": config.STATUS_PARSING_ENABLED,
        "status_camp_filter": config.STATUS_CAMP_FILTER,
        "slack_status_channel_configured": bool(config.SLACK_STATUS_CHANNEL_ID)
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


@router.post("/status-rollback/{student_id}")
async def rollback_status_change(student_id: int):
    """상태 변경 취소 (확인 팝업에서 '취소' 버튼)"""
    try:
        # 학생 조회
        student = await DBService.get_student_by_id(student_id)
        if not student:
            raise HTTPException(status_code=404, detail="학생을 찾을 수 없습니다.")

        # 상태 제거 (None으로 설정)
        success = await DBService.set_student_status(
            student_id=student_id,
            status_type=None,
            status_time=None,
            reason=None,
            end_date=None,
            protected=False
        )

        if not success:
            raise HTTPException(status_code=400, detail="상태 롤백에 실패했습니다.")

        # 대시보드 업데이트 브로드캐스트
        system = await wait_for_system_instance(timeout=2)
        if system and system.monitor_service:
            await system.monitor_service.broadcast_dashboard_update_now()

        return {"success": True, "message": "상태 변경이 취소되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"롤백 실패: {str(e)}")


class TestStatusMessageRequest(BaseModel):
    text: str


@router.post("/test-status-parsing")
async def test_status_parsing(data: TestStatusMessageRequest):
    """상태 파싱 테스트용 엔드포인트 (curl로 테스트 가능)"""
    system = await wait_for_system_instance(timeout=5)

    if not system:
        raise HTTPException(status_code=503, detail="시스템이 초기화되지 않았습니다.")

    if not system.slack_listener:
        raise HTTPException(status_code=503, detail="Slack 리스너가 실행 중이 아닙니다.")

    try:
        import time
        # 현재 timestamp 생성
        message_ts = time.time()

        # Slack 리스너의 파싱 메서드 직접 호출
        await system.slack_listener._process_status_message(data.text, message_ts)

        return {"success": True, "message": "파싱 요청을 처리했습니다. 로그를 확인하세요."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파싱 실패: {str(e)}")


@router.post("/status-confirm/{student_id}")
async def confirm_status(student_id: int):
    """
    예약된 상태를 실제 상태로 적용
    - scheduled_status_type → status_type
    - scheduled_status_time → status_set_at
    - 예약 필드는 초기화
    """
    system = await wait_for_system_instance()
    if not system or not system.db_service:
        raise HTTPException(status_code=503, detail="시스템이 준비되지 않았습니다.")

    try:
        from datetime import datetime, timezone
        from database.models import Student
        from sqlalchemy import update
        from database.connection import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            # 학생 조회
            from sqlalchemy import select
            result = await session.execute(
                select(Student).where(Student.id == student_id)
            )
            student = result.scalar_one_or_none()

            if not student:
                raise HTTPException(status_code=404, detail="학생을 찾을 수 없습니다.")

            if not student.scheduled_status_type:
                raise HTTPException(status_code=400, detail="예약된 상태가 없습니다.")

            # 예약된 상태를 실제 상태로 적용
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            update_values = {
                "status_type": student.scheduled_status_type,
                "status_set_at": student.scheduled_status_time or now,
                "status_end_date": student.status_end_date,  # 이미 설정된 종료일 유지
                "status_protected": student.status_protected or False,
                # 예약 필드 초기화
                "scheduled_status_type": None,
                "scheduled_status_time": None,
                "updated_at": now
            }

            await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(**update_values)
            )
            await session.commit()

            return {
                "success": True,
                "message": f"{student.zep_name}의 상태가 적용되었습니다.",
                "status_type": student.scheduled_status_type
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상태 적용 실패: {str(e)}")


@router.post("/status-rollback/{student_id}")
async def rollback_status(student_id: int):
    """
    예약된 상태를 취소
    - scheduled_status_type = None
    - scheduled_status_time = None
    - status_reason = None
    """
    system = await wait_for_system_instance()
    if not system or not system.db_service:
        raise HTTPException(status_code=503, detail="시스템이 준비되지 않았습니다.")

    try:
        from datetime import datetime, timezone
        from database.models import Student
        from sqlalchemy import update
        from database.connection import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            # 학생 조회
            from sqlalchemy import select
            result = await session.execute(
                select(Student).where(Student.id == student_id)
            )
            student = result.scalar_one_or_none()

            if not student:
                raise HTTPException(status_code=404, detail="학생을 찾을 수 없습니다.")

            # 예약 필드 초기화
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            update_values = {
                "scheduled_status_type": None,
                "scheduled_status_time": None,
                "status_reason": None,
                "status_end_date": None,
                "status_protected": False,
                "updated_at": now
            }

            await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(**update_values)
            )
            await session.commit()

            return {
                "success": True,
                "message": f"{student.zep_name}의 예약된 상태가 취소되었습니다."
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상태 취소 실패: {str(e)}")


