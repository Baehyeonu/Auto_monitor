"""
대시보드 API
"""
from typing import Optional
from datetime import datetime, timezone, date, timedelta
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


async def _get_reset_time() -> Optional[datetime]:
    """초기화 시간 반환"""
    system = await wait_for_system_instance(timeout=2)
    if system and system.monitor_service and system.monitor_service.reset_time:
        return system.monitor_service.reset_time
    
    # reset_time이 없으면 config에서 계산
    if config.DAILY_RESET_TIME:
        from zoneinfo import ZoneInfo
        try:
            reset_time = datetime.strptime(config.DAILY_RESET_TIME, "%H:%M").time()
            today = date.today()
            seoul_tz = ZoneInfo("Asia/Seoul")
            reset_dt_local = datetime.combine(today, reset_time).replace(tzinfo=seoul_tz)
            now_local = datetime.now(seoul_tz)
            
            # 현재 시간이 초기화 시간 이전이면 어제 초기화 시간 사용
            if now_local < reset_dt_local:
                reset_dt_local = reset_dt_local - timedelta(days=1)
            
            return reset_dt_local.astimezone(timezone.utc)
        except ValueError:
            pass
    
    return None


def _is_not_joined(student, joined_today: set, now: datetime, reset_time: Optional[datetime] = None) -> bool:
    """
    특이사항(미접속) 여부 판단

    조건:
    1. 휴가, 결석 상태인 학생은 특이사항으로 분류
    2. 외출, 조퇴는 퇴장(left)으로 분류
    3. 초기화 후 실제 입장 이벤트가 없었던 학생은 특이사항

    Args:
        student: Student 객체
        joined_today: 오늘 접속한 학생 ID 집합
        now: 현재 시간 (UTC)
        reset_time: 초기화 시간 (UTC, None이면 config에서 계산)

    Returns:
        특이사항이면 True
    """
    # 관리자는 제외
    if student.is_admin:
        return False

    # 외출, 조퇴, 휴가, 결석, 지각 등 status_type이 있으면 무조건 특이사항
    if student.status_type in ['leave', 'early_leave', 'vacation', 'absence', 'late']:
        return True

    # joined_today에 포함되어 있으면 접속한 것으로 간주 (특이사항 아님)
    if student.id in joined_today:
        return False

    # joined_today에 없으면 특이사항
    # joined_today는 슬랙 동기화 시 실제로 오늘 입장 이벤트가 있었던 학생들만 포함됨
    return True


@router.get("/overview")
async def get_overview():
    """전체 현황 조회"""
    students = await db_service.get_all_students()
    joined_today = await _get_joined_today()
    reset_time = await _get_reset_time()
    
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
        # 상태(status_type)가 있는 사람은 특이사항에만 포함 (카메라, 퇴장에서 제외)
        has_status = student.status_type in ['late', 'leave', 'early_leave', 'vacation', 'absence']

        # 1. 특이사항 체크
        is_not_joined = _is_not_joined(student, joined_today, now, reset_time)
        if is_not_joined:
            not_joined += 1

        # 2. 퇴장 체크 (상태가 있는 사람 제외)
        if not has_status and student.last_leave_time:
            leave_time = student.last_leave_time
            if leave_time.tzinfo is None:
                leave_time_utc = leave_time.replace(tzinfo=timezone.utc)
            else:
                leave_time_utc = leave_time
            leave_time_local = leave_time_utc.astimezone(ZoneInfo("Asia/Seoul"))
            leave_date = leave_time_local.date()

            # 오늘 퇴장한 학생
            if leave_date == today:
                left += 1

        # 3. 카메라 상태 체크 (입장한 사람 중 상태가 없고 퇴장하지 않은 사람만)
        if not has_status and student.id in joined_today and not student.last_leave_time:
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
    reset_time = await _get_reset_time()
    
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
        has_status = student.status_type in ['late', 'leave', 'early_leave', 'vacation', 'absence']

        # not_joined 값 계산
        is_not_joined = _is_not_joined(student, joined_today, now, reset_time)

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
            "not_joined": is_not_joined
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
            today = date.today()
            from zoneinfo import ZoneInfo

            if not has_status and student.last_leave_time:
                leave_time = student.last_leave_time
                if leave_time.tzinfo is None:
                    leave_time_utc = leave_time.replace(tzinfo=timezone.utc)
                else:
                    leave_time_utc = leave_time
                leave_time_local = leave_time_utc.astimezone(ZoneInfo("Asia/Seoul"))
                leave_date = leave_time_local.date()

                # 오늘 퇴장한 학생
                if leave_date == today:
                    # 퇴장 학생은 not_joined를 false로 설정
                    status_data["not_joined"] = False
                    result.append(status_data)
        elif filter == "not_joined":
            # 미접속: 초기화 시간 이후 상태 변화 없거나, 퇴장 후 10시간 이상
            if is_not_joined:
                result.append(status_data)
    
    return {"students": result}


@router.get("/alerts")
async def get_recent_alerts(limit: int = Query(50, ge=1, le=100)):
    """최근 알림 목록"""
    return {"alerts": []}


