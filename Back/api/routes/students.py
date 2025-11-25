"""
학생 관리 API
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from database import DBService
from api.schemas.student import (
    StudentCreate,
    StudentUpdate,
    StudentResponse,
    AdminStatusUpdate,
)
from api.schemas.response import PaginatedResponse
from services.admin_manager import admin_manager


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
            filtered_students = [s for s in filtered_students if not s.is_cam_on and not s.last_leave_time]
        elif status == "left":
            filtered_students = [s for s in filtered_students if s.last_leave_time is not None]
        elif status == "not_joined":
            pass  # TODO: joined_today 로직 필요
    
    if search:
        filtered_students = [s for s in filtered_students if search.lower() in s.zep_name.lower()]
    
    total = len(filtered_students)
    start = (page - 1) * limit
    end = start + limit
    paginated = filtered_students[start:end]
    
    return {
        "data": paginated,
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


