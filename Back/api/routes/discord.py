"""
Discord 멤버 관리 API
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import DBService
from api.routes.settings import wait_for_system_instance

router = APIRouter()
db_service = DBService()


class DiscordMember(BaseModel):
    """Discord 멤버 정보"""
    # JS 숫자 정밀도 손실을 방지하기 위해 문자열로 반환
    discord_id: str
    discord_name: str
    display_name: str
    is_student: bool


class MemberRegistrationRequest(BaseModel):
    """멤버 등록 요청"""
    members: List[Dict[str, Any]]  # [{discord_id, display_name}, ...]


class RegistrationResult(BaseModel):
    """등록 결과"""
    created: int
    already_exists: int
    failed: int
    errors: List[str]
    details: List[Dict[str, str]]  # 각 멤버별 상세 결과


@router.get("/members", response_model=List[DiscordMember])
async def get_discord_members():
    """
    Discord 서버의 모든 멤버 가져오기
    학생 패턴(영어+숫자+한글) 자동 감지
    """
    system = await wait_for_system_instance(timeout=5)

    if not system or not system.discord_bot:
        raise HTTPException(
            status_code=503,
            detail="Discord 봇이 실행되지 않았습니다."
        )

    try:
        members = await system.discord_bot.get_guild_members()
        # 혹시라도 숫자로 들어온 경우 문자열로 보정
        return [
            {
                **member,
                "discord_id": str(member.get("discord_id"))
            } for member in members
        ]

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Discord 멤버 가져오기 실패: {str(e)}"
        )


@router.post("/members/register", response_model=RegistrationResult)
async def register_discord_members(request: MemberRegistrationRequest):
    """
    선택한 Discord 멤버들을 학생으로 일괄 등록
    """
    system = await wait_for_system_instance(timeout=5)

    if not system or not system.discord_bot:
        raise HTTPException(
            status_code=503,
            detail="Discord 봇이 실행되지 않았습니다."
        )

    created = 0
    already_exists = 0
    failed = 0
    errors = []
    details = []

    for member_data in request.members:
        discord_id = member_data.get("discord_id")
        display_name = member_data.get("display_name")

        if not discord_id or not display_name:
            failed += 1
            errors.append(f"잘못된 데이터: discord_id 또는 display_name 누락")
            details.append({
                "name": display_name or "Unknown",
                "status": "failed",
                "reason": "데이터 누락"
            })
            continue

        try:
            try:
                # 문자열로 넘어온 Discord ID를 안전하게 정수로 변환
                discord_id_int = int(str(discord_id))
            except (TypeError, ValueError):
                raise ValueError("discord_id가 올바른 숫자 형식이 아닙니다.")

            # Discord ID로 중복 체크
            existing = await db_service.get_student_by_discord_id(discord_id_int)
            if existing:
                already_exists += 1
                details.append({
                    "name": display_name,
                    "status": "already_exists",
                    "reason": f"이미 '{existing.zep_name}'으로 등록됨"
                })
                continue

            # Discord 이름에서 한글 이름만 추출
            korean_name = system.discord_bot._extract_name_only(display_name)

            # 한글 이름 중복 체크
            existing_zep = await db_service.get_student_by_zep_name(korean_name)
            if existing_zep:
                already_exists += 1
                details.append({
                    "name": display_name,
                    "status": "already_exists",
                    "reason": f"한글 이름 '{korean_name}' 이미 등록됨"
                })
                continue

            # 학생 등록 (한글 이름으로 저장)
            await db_service.add_student(korean_name, discord_id_int)
            created += 1
            details.append({
                "name": display_name,
                "status": "created",
                "zep_name": korean_name
            })

        except Exception as e:
            failed += 1
            errors.append(f"{display_name}: {str(e)}")
            details.append({
                "name": display_name,
                "status": "failed",
                "reason": str(e)
            })

    return {
        "created": created,
        "already_exists": already_exists,
        "failed": failed,
        "errors": errors,
        "details": details
    }
