"""
FastAPI + WebSocket 통합 서버
"""
import os
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import students, dashboard, settings, reports, discord
from api.websocket_manager import manager

app = FastAPI(
    title="ZEP Monitor API",
    version="1.0.0",
    description="ZEP 학생 모니터링 시스템 API"
)

app.state.system_instance = None

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 시스템 인스턴스 확인 및 대기"""
    import asyncio
    import main
    
    max_wait = 30
    waited = 0
    
    while waited < max_wait:
        try:
            if main._system_instance is not None:
                system = main._system_instance
                if system.monitor_service:
                    return
        except Exception:
            pass
        
        await asyncio.sleep(1)
        waited += 1

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # 개발 모드 (Vite)
        "http://localhost:3000",  # Docker 프론트엔드
        "http://localhost",       # Docker 프론트엔드 (nginx 기본 포트)
        "http://frontend:80",     # Docker 내부 네트워크
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(students.router, prefix="/api/v1/students", tags=["students"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(discord.router, prefix="/api/v1/discord", tags=["discord"])

frontend_dist_path = Path(__file__).parent.parent / "Front" / "dist"
if not frontend_dist_path.exists():
    frontend_dist_path = Path(__file__).parent.parent.parent / "Front" / "dist"
if frontend_dist_path.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist_path / "assets")), name="assets")
    
    @app.get("/")
    async def serve_index():
        """프론트엔드 메인 페이지"""
        return FileResponse(str(frontend_dist_path / "index.html"))
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """프론트엔드 파일 서빙 (SPA 라우팅 지원)"""
        if full_path.startswith("api/") or full_path.startswith("ws") or full_path == "health":
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        
        file_path = frontend_dist_path / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        
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
    except Exception:
        manager.disconnect(websocket)
