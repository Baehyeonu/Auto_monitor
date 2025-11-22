"""
리포트 API
"""
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from database import DBService


router = APIRouter()
db_service = DBService()


@router.get("/attendance")
async def get_attendance_report(
    start_date: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD)")
):
    """출석 리포트"""
    # TODO: 출석 데이터 수집 및 리포트 생성
    return {"message": "Not implemented yet"}


@router.get("/camera-status")
async def get_camera_status_report(
    start_date: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD)")
):
    """카메라 상태 리포트"""
    # TODO: 카메라 상태 이력 리포트 생성
    return {"message": "Not implemented yet"}


@router.get("/alerts")
async def get_alerts_report(
    start_date: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD)")
):
    """알림 리포트"""
    # TODO: 알림 이력 리포트 생성
    return {"message": "Not implemented yet"}


