"""
대시보드 API
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Query

from database import DBService
from config import config
from utils.dashboard_utils import build_overview, is_not_joined, has_special_status, is_left_today
from utils.system_utils import get_joined_today


router = APIRouter()
db_service = DBService()


@router.get("/overview")
async def get_overview():
    """전체 현황 조회"""
    students = await db_service.get_all_students()
    joined_today = await get_joined_today()
    now = datetime.now(timezone.utc)
    return build_overview(students, joined_today, now, config.CAMERA_OFF_THRESHOLD)


@router.get("/students")
async def get_dashboard_students(filter: str = Query("all", regex="^(all|camera_on|camera_off|left|not_joined)$")):
    """실시간 학생 상태 목록"""
    students = await db_service.get_all_students()
    joined_today = await get_joined_today()
    
    now = datetime.now(timezone.utc)
    result = []
    
    for student in students:
        elapsed_minutes = 0
        if student.last_status_change:
            last_change_utc = student.last_status_change
            if last_change_utc.tzinfo is None:
                last_change_utc = last_change_utc.replace(tzinfo=timezone.utc)
            elapsed_minutes = int((now - last_change_utc).total_seconds() / 60)
        
        # 상태가 있는 사람은 특이사항에만 포함
        has_status = has_special_status(student)

        # not_joined 값 계산
        not_joined_flag = is_not_joined(student, joined_today)

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
            "alert_count": student.alert_count,
            "not_joined": not_joined_flag,
            "status_type": student.status_type,
            "status_set_at": student.status_set_at.isoformat() if student.status_set_at else None
        }

        if filter == "all":
            result.append(status_data)
        elif filter == "camera_on" and not has_status and student.is_cam_on and student.id in joined_today and not student.last_leave_time:
            # 카메라 ON: 입장한 사람 중 상태가 없고 카메라 켠 학생만 (퇴장하지 않은 학생)
            result.append(status_data)
        elif filter == "camera_off" and not has_status and not student.is_cam_on and student.id in joined_today and not student.last_leave_time:
            # 카메라 OFF: 입장한 사람 중 상태가 없고 카메라 꺼진 학생만 (퇴장하지 않은 학생)
            result.append(status_data)
        elif filter == "left":
            # 오늘 날짜에 퇴장한 학생만 (로컬 시간 기준, 상태가 없는 사람만)
            if not has_status and is_left_today(student):
                # 퇴장 학생은 not_joined를 false로 설정
                status_data["not_joined"] = False
                result.append(status_data)
        elif filter == "not_joined":
            # 미접속: 초기화 시간 이후 상태 변화 없거나, 퇴장 후 10시간 이상
            if not_joined_flag:
                result.append(status_data)
    
    return {"students": result}


@router.get("/alerts")
async def get_recent_alerts(limit: int = Query(50, ge=1, le=100)):
    """최근 알림 목록"""
    return {"alerts": []}
