"""
FastAPI + WebSocket 통합 서버
"""
import os
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import students, dashboard, settings, reports
from api.websocket_manager import manager

# FastAPI 앱 생성
app = FastAPI(
    title="ZEP Monitor API",
    version="1.0.0",
    description="ZEP 학생 모니터링 시스템 API"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # 개발 모드 (Vite)
        "http://localhost:3000",  # Docker 프론트엔드
        "http://frontend:80",     # Docker 내부 네트워크
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(students.router, prefix="/api/v1/students", tags=["students"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])

# 프론트엔드 정적 파일 서빙 (프로덕션 빌드가 있는 경우)
frontend_dist_path = Path(__file__).parent.parent.parent / "Front" / "dist"
if frontend_dist_path.exists():
    # 정적 파일 (JS, CSS, 이미지 등)
    app.mount("/assets", StaticFiles(directory=str(frontend_dist_path / "assets")), name="assets")
    
    # 루트 경로 - index.html 반환
    @app.get("/")
    async def serve_index():
        """프론트엔드 메인 페이지"""
        return FileResponse(str(frontend_dist_path / "index.html"))
    
    # SPA 라우팅을 위한 catch-all 핸들러 (API 경로 제외)
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """프론트엔드 파일 서빙 (SPA 라우팅 지원)"""
        # API 및 WebSocket 경로는 제외 (이미 위에서 처리됨)
        if full_path.startswith("api/") or full_path.startswith("ws") or full_path == "health":
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        
        # 파일이 존재하면 반환
        file_path = frontend_dist_path / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        
        # 파일이 없으면 index.html 반환 (SPA 라우팅)
        return FileResponse(str(frontend_dist_path / "index.html"))


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 엔드포인트"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)
