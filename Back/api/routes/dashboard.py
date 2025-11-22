"""
대시보드 API
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Query

from database import DBService
from config import config


router = APIRouter()
db_service = DBService()


@router.get("/overview")
async def get_overview():
    """전체 현황 조회"""
    students = await db_service.get_all_students()
    
    camera_on = 0
    camera_off = 0
    left = 0
    not_joined = 0
    threshold_exceeded = 0
    
    now = datetime.now(timezone.utc)
    threshold_minutes = config.CAMERA_OFF_THRESHOLD
    
    for student in students:
        if student.last_leave_time:
            left += 1
        elif student.is_cam_on:
            camera_on += 1
        else:
            camera_off += 1
            # 임계값 초과 체크
            if student.last_status_change:
                last_change_utc = student.last_status_change
                if last_change_utc.tzinfo is None:
                    last_change_utc = last_change_utc.replace(tzinfo=timezone.utc)
                elapsed = (now - last_change_utc).total_seconds() / 60
                if elapsed >= threshold_minutes:
                    threshold_exceeded += 1
    
    return {
        "total_students": len(students),
        "camera_on": camera_on,
        "camera_off": camera_off,
        "left": left,
        "not_joined_today": not_joined,  # TODO: joined_today 로직 필요
        "threshold_exceeded": threshold_exceeded,
        "last_updated": now.isoformat()
    }


@router.get("/students")
async def get_dashboard_students(filter: str = Query("all", regex="^(all|camera_on|camera_off|left)$")):
    """실시간 학생 상태 목록"""
    students = await db_service.get_all_students()
    
    now = datetime.now(timezone.utc)
    result = []
    
    for student in students:
        # 경과 시간 계산
        elapsed_minutes = 0
        if student.last_status_change:
            last_change_utc = student.last_status_change
            if last_change_utc.tzinfo is None:
                last_change_utc = last_change_utc.replace(tzinfo=timezone.utc)
            elapsed_minutes = int((now - last_change_utc).total_seconds() / 60)
        
        status_data = {
            "id": student.id,
            "zep_name": student.zep_name,
            "discord_id": student.discord_id,
            "is_cam_on": student.is_cam_on,
            "last_status_change": student.last_status_change.isoformat() if student.last_status_change else None,
            "is_absent": student.is_absent,
            "absent_type": student.absent_type,
            "last_leave_time": student.last_leave_time.isoformat() if student.last_leave_time else None,
            "elapsed_minutes": elapsed_minutes,
            "is_threshold_exceeded": elapsed_minutes >= config.CAMERA_OFF_THRESHOLD,
            "alert_count": student.alert_count
        }
        
        # 필터링
        if filter == "all":
            result.append(status_data)
        elif filter == "camera_on" and student.is_cam_on and not student.last_leave_time:
            result.append(status_data)
        elif filter == "camera_off" and not student.is_cam_on and not student.last_leave_time:
            result.append(status_data)
        elif filter == "left" and student.last_leave_time:
            result.append(status_data)
    
    return {"students": result}


@router.get("/alerts")
async def get_recent_alerts(limit: int = Query(50, ge=1, le=100)):
    """최근 알림 목록"""
    # TODO: alerts 테이블 추가 후 구현
    return {"alerts": []}


