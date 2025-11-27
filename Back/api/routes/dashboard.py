"""
대시보드 API
"""
from datetime import datetime, timezone, date
from fastapi import APIRouter, Query

from database import DBService
from config import config
from api.routes.settings import wait_for_system_instance


router = APIRouter()
db_service = DBService()


async def _get_joined_today():
    """오늘 접속한 학생 ID 집합 반환"""
    system = await wait_for_system_instance(timeout=2)
    if system and system.slack_listener:
        return system.slack_listener.get_joined_students_today()
    return set()


@router.get("/overview")
async def get_overview():
    """전체 현황 조회"""
    students = await db_service.get_all_students()
    joined_today = await _get_joined_today()
    
    camera_on = 0
    camera_off = 0
    left = 0
    not_joined = 0
    threshold_exceeded = 0
    
    now = datetime.now(timezone.utc)
    threshold_minutes = config.CAMERA_OFF_THRESHOLD
    
    non_admin_students = [s for s in students if not s.is_admin]
    today = date.today()
    
    for student in non_admin_students:
        # 오늘 퇴장한 학생
        if student.last_leave_time:
            leave_time = student.last_leave_time
            if leave_time.tzinfo is None:
                leave_date = leave_time.date()
            else:
                leave_date = leave_time.astimezone(timezone.utc).date()
            
            if leave_date == today:
                left += 1
            # 어제 이전에 퇴장한 학생은 미접속으로 분류
            elif leave_date < today:
                if student.id not in joined_today:
                    not_joined += 1
        # 미접속: 오늘 접속하지 않았고, 퇴장하지 않은 학생
        elif student.id not in joined_today:
            not_joined += 1
        # 접속 중인 학생
        elif student.is_cam_on:
            camera_on += 1
        else:
            camera_off += 1
            if student.last_status_change:
                last_change_utc = student.last_status_change
                if last_change_utc.tzinfo is None:
                    last_change_utc = last_change_utc.replace(tzinfo=timezone.utc)
                elapsed = (now - last_change_utc).total_seconds() / 60
                if elapsed >= threshold_minutes:
                    threshold_exceeded += 1
    
    return {
        "total_students": len(non_admin_students),
        "camera_on": camera_on,
        "camera_off": camera_off,
        "left": left,
        "not_joined_today": not_joined,
        "threshold_exceeded": threshold_exceeded,
        "last_updated": now.isoformat()
    }


@router.get("/students")
async def get_dashboard_students(filter: str = Query("all", regex="^(all|camera_on|camera_off|left|not_joined)$")):
    """실시간 학생 상태 목록"""
    students = await db_service.get_all_students()
    joined_today = await _get_joined_today()
    
    now = datetime.now(timezone.utc)
    result = []
    
    for student in students:
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
        
        if filter == "all":
            result.append(status_data)
        elif filter == "camera_on" and student.is_cam_on and not student.last_leave_time:
            result.append(status_data)
        elif filter == "camera_off" and not student.is_cam_on and not student.last_leave_time and student.id in joined_today:
            # 카메라 OFF: 접속했지만 카메라가 꺼진 학생만 (미접속자 제외)
            result.append(status_data)
        elif filter == "left":
            # 오늘 날짜에 퇴장한 학생만
            if student.last_leave_time:
                leave_time = student.last_leave_time
                if leave_time.tzinfo is None:
                    leave_date = leave_time.date()
                else:
                    leave_date = leave_time.astimezone(timezone.utc).date()
                if leave_date == date.today():
                    result.append(status_data)
        elif filter == "not_joined":
            # 미접속: 오늘 접속하지 않았고, 오늘 퇴장하지 않은 학생
            if student.id not in joined_today and not student.is_admin:
                if student.last_leave_time is None:
                    result.append(status_data)
                else:
                    leave_time = student.last_leave_time
                    if leave_time.tzinfo is None:
                        leave_date = leave_time.date()
                    else:
                        leave_date = leave_time.astimezone(timezone.utc).date()
                    # 어제 이전에 퇴장한 경우만 미접속
                    if leave_date < date.today():
                        result.append(status_data)
    
    return {"students": result}


@router.get("/alerts")
async def get_recent_alerts(limit: int = Query(50, ge=1, le=100)):
    """최근 알림 목록"""
    return {"alerts": []}


