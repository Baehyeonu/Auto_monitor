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
    
    from zoneinfo import ZoneInfo
    
    for student in non_admin_students:
        # 1. 미접속 체크 (퇴장보다 우선)
        # - last_status_change가 어제 이전이면 미접속
        # - 또는 last_leave_time이 어제 이전이면 미접속
        is_not_joined = False
        
        if student.last_status_change:
            status_change = student.last_status_change
            if status_change.tzinfo is None:
                status_change_utc = status_change.replace(tzinfo=timezone.utc)
            else:
                status_change_utc = status_change
            status_change_local = status_change_utc.astimezone(ZoneInfo("Asia/Seoul"))
            status_date = status_change_local.date()
            
            # 어제 이전에 상태 변경이 있었으면 미접속
            if status_date < today:
                is_not_joined = True
        
        # last_leave_time이 어제 이전이면 미접속
        if student.last_leave_time:
            leave_time = student.last_leave_time
            if leave_time.tzinfo is None:
                leave_time_utc = leave_time.replace(tzinfo=timezone.utc)
            else:
                leave_time_utc = leave_time
            leave_time_local = leave_time_utc.astimezone(ZoneInfo("Asia/Seoul"))
            leave_date = leave_time_local.date()
            
            if leave_date < today:
                # 어제 이전에 퇴장한 학생 → 미접속
                is_not_joined = True
            elif leave_date == today:
                # 오늘 퇴장한 학생 → 퇴장 (미접속이 아닌 경우만)
                if not is_not_joined:
                    left += 1
                    continue
        
        # joined_today에 없고 시간 정보도 없으면 미접속
        if not is_not_joined and student.id not in joined_today and not student.last_status_change and not student.last_leave_time:
            is_not_joined = True
        
        if is_not_joined:
            not_joined += 1
            continue
        
        # 접속 중인 학생 (카메라 상태)
        if student.is_cam_on:
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
            # 오늘 날짜에 퇴장한 학생만 (로컬 시간 기준)
            # 단, 미접속 조건에 해당하지 않는 경우만
            today = date.today()
            from zoneinfo import ZoneInfo
            
            # 미접속 체크 (퇴장보다 우선)
            is_not_joined = False
            
            if student.last_status_change:
                status_change = student.last_status_change
                if status_change.tzinfo is None:
                    status_change_utc = status_change.replace(tzinfo=timezone.utc)
                else:
                    status_change_utc = status_change
                status_change_local = status_change_utc.astimezone(ZoneInfo("Asia/Seoul"))
                status_date = status_change_local.date()
                if status_date < today:
                    is_not_joined = True
            
            if student.last_leave_time:
                leave_time = student.last_leave_time
                if leave_time.tzinfo is None:
                    leave_time_utc = leave_time.replace(tzinfo=timezone.utc)
                else:
                    leave_time_utc = leave_time
                leave_time_local = leave_time_utc.astimezone(ZoneInfo("Asia/Seoul"))
                leave_date = leave_time_local.date()
                
                # 어제 이전에 퇴장한 학생은 미접속
                if leave_date < today:
                    is_not_joined = True
                # 오늘 퇴장한 학생이면서 미접속이 아닌 경우만 퇴장으로 표시
                elif leave_date == today and not is_not_joined:
                    result.append(status_data)
        elif filter == "not_joined":
            # 미접속: last_status_change가 어제 이전이거나 시간 정보가 없는 학생
            today = date.today()
            from zoneinfo import ZoneInfo
            
            if student.id not in joined_today and not student.is_admin:
                # last_status_change를 기준으로 판단 (가장 정확함)
                if student.last_status_change:
                    status_change = student.last_status_change
                    if status_change.tzinfo is None:
                        status_change_utc = status_change.replace(tzinfo=timezone.utc)
                    else:
                        status_change_utc = status_change
                    status_change_local = status_change_utc.astimezone(ZoneInfo("Asia/Seoul"))
                    status_date = status_change_local.date()
                    # 어제 이전 날짜면 미접속
                    if status_date < today:
                        result.append(status_data)
                # 시간 정보가 없으면 미접속
                elif not student.last_status_change and not student.last_leave_time:
                    result.append(status_data)
    
    return {"students": result}


@router.get("/alerts")
async def get_recent_alerts(limit: int = Query(50, ge=1, le=100)):
    """최근 알림 목록"""
    return {"alerts": []}


