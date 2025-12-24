"""
학생 관리 API
"""
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import DBService
from api.schemas.student import (
    StudentCreate,
    StudentUpdate,
    StudentResponse,
    AdminStatusUpdate,
    StudentStatusUpdate,
)
from api.schemas.response import PaginatedResponse
from services.admin_manager import admin_manager
from utils.system_utils import get_joined_today
from utils.dashboard_utils import is_not_joined, has_special_status, is_left_today


class SendDMRequest(BaseModel):
    dm_type: str


router = APIRouter()
db_service = DBService()


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
    joined_today = await get_joined_today()
    
    is_admin_bool = None
    if is_admin is not None:
        is_admin_bool = is_admin.lower() in ('true', '1', 'yes')
    
    if is_admin_bool is not None:
        students = [s for s in students if s.is_admin == is_admin_bool]
    
    filtered_students = students
    
    if status:
        if status == "camera_on":
            # 카메라 ON: 입장한 사람 중 상태가 없고 카메라 켠 학생만 (퇴장하지 않은 학생)
            filtered_students = [
                s for s in filtered_students
                if not has_special_status(s)
                and s.is_cam_on
                and s.id in joined_today
                and not s.last_leave_time
            ]
        elif status == "camera_off":
            # 카메라 OFF: 입장한 사람 중 상태가 없고 카메라 꺼진 학생만 (퇴장하지 않은 학생)
            filtered_students = [
                s for s in filtered_students
                if not has_special_status(s)
                and not s.is_cam_on
                and s.id in joined_today
                and not s.last_leave_time
            ]
        elif status == "left":
            # 오늘 날짜에 퇴장한 학생만 필터링 (로컬 시간 기준, 상태가 없는 사람만)
            result = []
            for s in filtered_students:
                if not has_special_status(s) and is_left_today(s):
                    result.append(s)
            filtered_students = result
        elif status == "not_joined":
            # 특이사항: 휴가, 결석 상태이거나 초기화 후 입장 이력이 없는 경우
            result = []
            for s in filtered_students:
                if is_not_joined(s, joined_today):
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
        not_joined_flag = is_not_joined(student, joined_today)

        # status 필터가 left인 경우, 퇴장한 학생이므로 not_joined는 false로 설정
        if status == "left":
            not_joined_flag = False

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
            "status_type": student.status_type,
            "status_set_at": student.status_set_at,
            "alarm_blocked_until": student.alarm_blocked_until,
            "status_auto_reset_date": student.status_auto_reset_date,
            "created_at": student.created_at,
            "updated_at": student.updated_at,
            "not_joined": not_joined_flag
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
    existing = await db_service.get_student_by_zep_name_exact(data.zep_name)
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
        # DM 전송 실패 시 웹페이지 로그에 표시
        error_message = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - 사용자가 DM을 차단했거나 Discord 봇과 서버를 공유하지 않습니다"
        await manager.broadcast_system_log(
            level="error",
            source="discord",
            event_type="dm_failed",
            message=error_message,
            student_name=student.zep_name,
            student_id=student.id
        )
        raise HTTPException(status_code=500, detail=f"Failed to send DM to {student.zep_name}. Check Discord bot logs for details.")


@router.put("/{student_id}/status", response_model=StudentResponse)
async def update_student_status(student_id: int, data: StudentStatusUpdate):
    """학생 상태 설정 (지각, 외출, 조퇴, 휴가, 결석)"""
    student = await db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    success = await db_service.set_student_status(student_id, data.status_type, data.status_time)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update student status")
    
    updated_student = await db_service.get_student_by_id(student_id)
    return updated_student
