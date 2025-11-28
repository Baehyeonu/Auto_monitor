"""
학생 관리 API
"""
from typing import Optional, List
from datetime import datetime, timezone, date, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import DBService
from api.schemas.student import (
    StudentCreate,
    StudentUpdate,
    StudentResponse,
    AdminStatusUpdate,
)
from api.schemas.response import PaginatedResponse
from services.admin_manager import admin_manager
from api.routes.settings import wait_for_system_instance
from config import config


class SendDMRequest(BaseModel):
    dm_type: str


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
    미접속 여부 판단
    
    조건:
    1. 초기화 시간 이후 상태 변화가 없으면 미접속
    2. 퇴장 후 10시간 이상 지났으면 미접속
    
    Args:
        student: Student 객체
        joined_today: 오늘 접속한 학생 ID 집합
        now: 현재 시간 (UTC)
        reset_time: 초기화 시간 (UTC, None이면 config에서 계산)
        
    Returns:
        미접속이면 True
    """
    # 관리자는 제외
    if student.is_admin:
        return False
    
    # joined_today에 포함되어 있으면 접속한 것으로 간주 (미접속 아님)
    if student.id in joined_today:
        return False
    
    # 초기화 시간 계산
    if reset_time is None:
        if config.DAILY_RESET_TIME:
            from zoneinfo import ZoneInfo
            try:
                reset_time_obj = datetime.strptime(config.DAILY_RESET_TIME, "%H:%M").time()
                today = date.today()
                seoul_tz = ZoneInfo("Asia/Seoul")
                reset_dt_local = datetime.combine(today, reset_time_obj).replace(tzinfo=seoul_tz)
                now_local = datetime.now(seoul_tz)
                
                # 현재 시간이 초기화 시간 이전이면 어제 초기화 시간 사용
                if now_local < reset_dt_local:
                    reset_dt_local = reset_dt_local - timedelta(days=1)
                
                reset_time = reset_dt_local.astimezone(timezone.utc)
            except ValueError:
                # 초기화 시간이 설정되지 않았으면 항상 접속한 것으로 간주
                return False
        else:
            # 초기화 시간이 설정되지 않았으면 항상 접속한 것으로 간주
            return False
    
    # 조건 1: 초기화 시간 이후 상태 변화가 없으면 미접속
    if student.last_status_change:
        status_change = student.last_status_change
        if status_change.tzinfo is None:
            status_change_utc = status_change.replace(tzinfo=timezone.utc)
        else:
            status_change_utc = status_change
        
        # 초기화 시간 이후에 상태 변화가 있으면 접속한 것으로 간주 (미접속 아님)
        if status_change_utc >= reset_time:
            return False
        # 초기화 시간 이전이면 미접속
        else:
            return True
    else:
        # last_status_change가 없으면 미접속
        return True
    
    # 조건 2: 퇴장 후 10시간 이상 지났으면 미접속
    if student.last_leave_time:
        leave_time = student.last_leave_time
        if leave_time.tzinfo is None:
            leave_time_utc = leave_time.replace(tzinfo=timezone.utc)
        else:
            leave_time_utc = leave_time
        
        # 퇴장 후 경과 시간 계산
        elapsed = (now - leave_time_utc).total_seconds() / 3600  # 시간 단위
        
        # 10시간 이상 지났으면 미접속
        if elapsed >= 10:
            return True
    
    return False


@router.get("", response_model=PaginatedResponse[StudentResponse])
async def get_students(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, regex="^(camera_on|camera_off|left|not_joined)$"),
    search: Optional[str] = None,
    is_admin: Optional[str] = Query(None, description="관리자 여부 필터 (true: 관리자만, false: 학생만, null: 전체)")
):
    """학생 목록 조회"""
    students = await db_service.get_all_students()
    joined_today = await _get_joined_today()
    reset_time = await _get_reset_time()
    
    is_admin_bool = None
    if is_admin is not None:
        is_admin_bool = is_admin.lower() in ('true', '1', 'yes')
    
    if is_admin_bool is not None:
        students = [s for s in students if s.is_admin == is_admin_bool]
    
    filtered_students = students
    
    if status:
        if status == "camera_on":
            filtered_students = [s for s in filtered_students if s.is_cam_on and not s.last_leave_time]
        elif status == "camera_off":
            # 카메라 OFF: 접속했지만 카메라가 꺼진 학생만 (미접속자 제외)
            filtered_students = [s for s in filtered_students if not s.is_cam_on and not s.last_leave_time and s.id in joined_today]
        elif status == "left":
            # 오늘 날짜에 퇴장한 학생만 필터링 (로컬 시간 기준)
            # 단, 미접속 조건에 해당하지 않는 경우만
            today = date.today()
            now = datetime.now(timezone.utc)
            result = []
            for s in filtered_students:
                # 미접속 체크 (퇴장보다 우선)
                is_not_joined = _is_not_joined(s, joined_today, now, reset_time)
                
                if s.last_leave_time and not is_not_joined:
                    leave_time = s.last_leave_time
                    # naive datetime을 UTC로 가정하고 로컬 시간으로 변환
                    if leave_time.tzinfo is None:
                        leave_time_utc = leave_time.replace(tzinfo=timezone.utc)
                    else:
                        leave_time_utc = leave_time
                    # 로컬 시간대(Asia/Seoul, UTC+9)로 변환
                    from zoneinfo import ZoneInfo
                    leave_time_local = leave_time_utc.astimezone(ZoneInfo("Asia/Seoul"))
                    leave_date = leave_time_local.date()
                    
                    # 오늘 퇴장한 학생이면서 미접속이 아닌 경우만 퇴장으로 표시
                    if leave_date == today:
                        result.append(s)
            filtered_students = result
        elif status == "not_joined":
            # 미접속: 초기화 시간 이후 상태 변화 없거나, 퇴장 후 10시간 이상
            now = datetime.now(timezone.utc)
            result = []
            for s in filtered_students:
                if _is_not_joined(s, joined_today, now, reset_time):
                    result.append(s)
            filtered_students = result
    
    if search:
        filtered_students = [s for s in filtered_students if search.lower() in s.zep_name.lower()]
    
    total = len(filtered_students)
    start = (page - 1) * limit
    end = start + limit
    paginated = filtered_students[start:end]
    
    result_data = []
    now = datetime.now(timezone.utc)
    for student in paginated:
        # 미접속자 판단: 초기화 시간 이후 상태 변화 없거나, 퇴장 후 10시간 이상
        is_not_joined = _is_not_joined(student, joined_today, now, reset_time)
        
        student_dict = {
            "id": student.id,
            "zep_name": student.zep_name,
            "discord_id": student.discord_id,
            "is_admin": student.is_admin,
            "is_cam_on": student.is_cam_on,
            "last_status_change": student.last_status_change,
            "last_alert_sent": student.last_alert_sent,
            "alert_count": student.alert_count,
            "response_status": student.response_status,
            "is_absent": student.is_absent,
            "absent_type": student.absent_type,
            "last_leave_time": student.last_leave_time,
            "created_at": student.created_at,
            "updated_at": student.updated_at,
            "not_joined": is_not_joined
        }
        result_data.append(student_dict)
    
    return {
        "data": result_data,
        "total": total,
        "page": page,
        "limit": limit
    }


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(student_id: int):
    """학생 상세 조회"""
    student = await db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.post("", response_model=StudentResponse)
async def create_student(data: StudentCreate):
    """학생 등록"""
    existing = await db_service.get_student_by_zep_name(data.zep_name)
    if existing:
        raise HTTPException(status_code=400, detail="Student already exists")
    
    student = await db_service.add_student(data.zep_name, data.discord_id)
    return student


@router.put("/{student_id}", response_model=StudentResponse)
async def update_student(student_id: int, data: StudentUpdate):
    """학생 수정"""
    student = await db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if data.zep_name and data.zep_name != student.zep_name:
        existing = await db_service.get_student_by_zep_name(data.zep_name)
        if existing and existing.id != student_id:
            raise HTTPException(status_code=400, detail="ZEP name already exists")
    
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.delete("/{student_id}")
async def delete_student(student_id: int):
    """학생 삭제 (관리자는 삭제 불가)"""
    student = await db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if student.is_admin:
        raise HTTPException(
            status_code=400,
            detail="관리자는 삭제할 수 없습니다. 먼저 학생 상태로 변경해주세요."
        )
    
    success = await db_service.delete_student(student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True, "message": "Student deleted"}


@router.delete("/bulk/all")
async def delete_all_students():
    """학생 전체 삭제 (관리자 제외)"""
    students = await db_service.get_all_students()
    student_ids = [s.id for s in students if not s.is_admin]
    
    deleted_count = 0
    failed_count = 0
    
    for student_id in student_ids:
        try:
            success = await db_service.delete_student(student_id)
            if success:
                deleted_count += 1
            else:
                failed_count += 1
        except Exception:
            failed_count += 1
    
    return {
        "success": True,
        "deleted": deleted_count,
        "failed": failed_count,
        "message": f"{deleted_count}명의 학생이 삭제되었습니다."
    }


@router.post("/bulk")
async def bulk_create_students(data: List[StudentCreate]):
    """학생 일괄 등록"""
    created = 0
    failed = 0
    errors = []
    
    for student_data in data:
        try:
            existing = await db_service.get_student_by_zep_name(student_data.zep_name)
            if existing:
                failed += 1
                errors.append(f"{student_data.zep_name}: already exists")
                continue
            
            await db_service.add_student(student_data.zep_name, student_data.discord_id)
            created += 1
        except Exception as e:
            failed += 1
            errors.append(f"{student_data.zep_name}: {str(e)}")
    
    return {"created": created, "failed": failed, "errors": errors}


@router.post("/{student_id}/status")
async def change_student_status(student_id: int, status: str):
    """학생 상태 변경 (외출/조퇴)"""
    student = await db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if status == 'leave':
        await db_service.set_absent_status(student_id, 'leave')
    elif status == 'early_leave':
        await db_service.set_absent_status(student_id, 'early_leave')
    elif status == 'active':
        await db_service.clear_absent_status(student_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    student = await db_service.get_student_by_id(student_id)
    return student


@router.post("/{student_id}/admin", response_model=StudentResponse)
async def update_admin_status(student_id: int, data: AdminStatusUpdate):
    """학생의 관리자 권한을 설정"""
    student = await db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    success = await db_service.set_admin_status(student_id, data.is_admin)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update admin status")

    await admin_manager.refresh()
    return await db_service.get_student_by_id(student_id)


@router.post("/{student_id}/send-dm")
async def send_dm_to_student(student_id: int, request: SendDMRequest):
    """학생에게 직접 DM 전송"""
    from api.routes.settings import wait_for_system_instance
    from api.websocket_manager import manager
    
    if request.dm_type not in ["camera_alert", "join_request", "face_not_visible"]:
        raise HTTPException(status_code=400, detail="Invalid dm_type")
    
    student = await db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if not student.discord_id:
        raise HTTPException(status_code=400, detail="Student does not have Discord ID")
    
    system = await wait_for_system_instance(timeout=2)
    if not system or not system.discord_bot:
        raise HTTPException(status_code=503, detail="Discord bot not available")
    
    success = False
    message = ""
    
    if request.dm_type == "camera_alert":
        success = await system.discord_bot.send_manual_camera_alert(student)
        message = f"DM 전송: {student.zep_name}님에게 카메라 켜주세요 알림"
    elif request.dm_type == "join_request":
        success = await system.discord_bot.send_manual_join_request(student)
        message = f"DM 전송: {student.zep_name}님에게 접속해 주세요 알림"
    elif request.dm_type == "face_not_visible":
        success = await system.discord_bot.send_face_not_visible_alert(student)
        message = f"DM 전송: {student.zep_name}님에게 화면에 얼굴이 안보여요 알림"
    
    if success:
        await manager.broadcast_system_log(
            level="info",
            source="discord",
            event_type="dm_sent",
            message=message,
            student_name=student.zep_name,
            student_id=student.id
        )
        return {"success": True, "message": "DM sent successfully"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to send DM to {student.zep_name}. Check Discord bot logs for details.")


