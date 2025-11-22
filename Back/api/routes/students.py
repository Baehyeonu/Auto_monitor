"""
학생 관리 API
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from database import DBService
from api.schemas.student import StudentCreate, StudentUpdate, StudentResponse
from api.schemas.response import PaginatedResponse
from config import config


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
    admin_ids = config.get_admin_ids()
    
    # 관리자 구분 필터링 (문자열로 받아서 변환)
    is_admin_bool = None
    if is_admin is not None:
        is_admin_bool = is_admin.lower() in ('true', '1', 'yes')
    
    # 디버깅: 관리자 ID 목록 출력
    print(f"🔍 [API] is_admin 파라미터: {is_admin} -> {is_admin_bool}")
    print(f"🔍 [API] 관리자 ID 목록: {admin_ids}")
    print(f"🔍 [API] 전체 학생 수: {len(students)}")
    
    if is_admin_bool is not None:
        if is_admin_bool:
            # 관리자만: Discord ID가 있고 관리자 목록에 포함된 경우
            if admin_ids:
                students = [s for s in students if s.discord_id is not None and s.discord_id in admin_ids]
                print(f"🔍 [API] 관리자 필터링 후: {len(students)}명")
            else:
                # 관리자 목록이 비어있으면 관리자 없음
                students = []
        else:
            # 학생만: Discord ID가 없거나, 있더라도 관리자 목록에 없는 경우
            if admin_ids:
                students = [s for s in students if s.discord_id is None or s.discord_id not in admin_ids]
                print(f"🔍 [API] 학생 필터링 후: {len(students)}명")
            else:
                # 관리자 목록이 비어있으면 모든 학생이 학생으로 간주
                pass  # students 그대로 사용
    
    # 필터링 로직
    filtered_students = students
    
    if status:
        if status == "camera_on":
            filtered_students = [s for s in filtered_students if s.is_cam_on and not s.last_leave_time]
        elif status == "camera_off":
            filtered_students = [s for s in filtered_students if not s.is_cam_on and not s.last_leave_time]
        elif status == "left":
            filtered_students = [s for s in filtered_students if s.last_leave_time is not None]
        elif status == "not_joined":
            # TODO: joined_today 로직 필요
            pass
    
    if search:
        filtered_students = [s for s in filtered_students if search.lower() in s.zep_name.lower()]
    
    # 페이지네이션
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
    
    # TODO: DBService에 update_student 메서드 추가 필요
    # 현재는 기본 정보만 업데이트 가능
    if data.zep_name and data.zep_name != student.zep_name:
        # 이름 중복 체크
        existing = await db_service.get_student_by_zep_name(data.zep_name)
        if existing and existing.id != student_id:
            raise HTTPException(status_code=400, detail="ZEP name already exists")
    
    # TODO: 실제 업데이트 로직 구현
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.delete("/{student_id}")
async def delete_student(student_id: int):
    """학생 삭제"""
    success = await db_service.delete_student(student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True, "message": "Student deleted"}


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


