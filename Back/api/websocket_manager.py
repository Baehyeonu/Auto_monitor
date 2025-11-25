"""
WebSocket 연결 관리
"""
from datetime import datetime
from typing import Dict, Set
from fastapi import WebSocket
import json
import asyncio


class ConnectionManager:
    def __init__(self):
        # 활성 연결들
        self.active_connections: Set[WebSocket] = set()
        # 대시보드 구독자들
        self.dashboard_subscribers: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """새 연결 수락"""
        await websocket.accept()
        self.active_connections.add(websocket)
        
        print(f"📡 [WebSocket] 새 연결 수락 (총 연결: {len(self.active_connections)}개)", flush=True)
        
        await self.send_personal_message(websocket, {
            "type": "CONNECTED",
            "payload": {
                "message": "WebSocket connected successfully",
                "client_id": str(id(websocket))
            },
            "timestamp": datetime.now().isoformat()
        })
    
    def disconnect(self, websocket: WebSocket):
        """연결 해제"""
        was_subscriber = websocket in self.dashboard_subscribers
        self.active_connections.discard(websocket)
        self.dashboard_subscribers.discard(websocket)
        
        subscriber_info = " (대시보드 구독자)" if was_subscriber else ""
        print(f"📡 [WebSocket] 연결 해제{subscriber_info} (남은 연결: {len(self.active_connections)}개, 구독자: {len(self.dashboard_subscribers)}명)", flush=True)
    
    async def handle_message(self, websocket: WebSocket, data: dict):
        """클라이언트 메시지 처리"""
        msg_type = data.get("type", "")
        
        if msg_type == "SUBSCRIBE_DASHBOARD":
            self.dashboard_subscribers.add(websocket)
            print(f"📡 [WebSocket] 대시보드 구독 추가 (총 구독자: {len(self.dashboard_subscribers)}명)", flush=True)
        
        elif msg_type == "UNSUBSCRIBE_DASHBOARD":
            self.dashboard_subscribers.discard(websocket)
            print(f"📡 [WebSocket] 대시보드 구독 해제 (남은 구독자: {len(self.dashboard_subscribers)}명)", flush=True)
        
        elif msg_type == "PING":
            await self.send_personal_message(websocket, {
                "type": "PONG",
                "payload": {},
                "timestamp": datetime.now().isoformat()
            })
        
        elif msg_type == "CHANGE_STUDENT_STATUS":
            # 학생 상태 변경 처리
            payload = data.get("payload", {})
            student_id = payload.get("student_id")
            status = payload.get("status")
            # TODO: DB 업데이트 로직 연결
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """특정 클라이언트에게 메시지 전송"""
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)
    
    async def broadcast_to_dashboard(self, message: dict):
        """대시보드 구독자들에게 브로드캐스트"""
        if not self.dashboard_subscribers:
            return
        
        async def send_to_client(websocket: WebSocket):
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect(websocket)
        
        await asyncio.gather(
            *[send_to_client(ws) for ws in self.dashboard_subscribers],
            return_exceptions=True
        )
    
    async def broadcast_student_status_changed(
        self, 
        student_id: int, 
        zep_name: str, 
        event_type: str,
        is_cam_on: bool,
        elapsed_minutes: int = 0
    ):
        """학생 상태 변경 브로드캐스트"""
        message = {
            "type": "STUDENT_STATUS_CHANGED",
            "payload": {
                "student_id": student_id,
                "zep_name": zep_name,
                "event_type": event_type,
                "is_cam_on": is_cam_on,
                "elapsed_minutes": elapsed_minutes
            },
            "timestamp": datetime.now().isoformat()
        }
        subscriber_count = len(self.dashboard_subscribers)
        if subscriber_count == 0:
            print(f"    ⚠️ [WebSocket] 구독자 없음 - 메시지 전송 안 됨 (구독자: {subscriber_count}명)", flush=True)
        else:
            print(f"    📡 [WebSocket] 구독자 {subscriber_count}명에게 전송 중...", flush=True)
        await self.broadcast_to_dashboard(message)
    
    async def broadcast_new_alert(
        self,
        alert_id: int,
        student_id: int,
        zep_name: str,
        alert_type: str,
        alert_message: str
    ):
        """새 알림 브로드캐스트"""
        message = {
            "type": "NEW_ALERT",
            "payload": {
                "id": alert_id,
                "student_id": student_id,
                "zep_name": zep_name,
                "alert_type": alert_type,
                "message": alert_message
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_dashboard(message)
    
    async def broadcast_dashboard_update(self, overview_data: dict):
        """대시보드 현황 업데이트 브로드캐스트"""
        message = {
            "type": "DASHBOARD_UPDATE",
            "payload": overview_data,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_dashboard(message)


# 전역 매니저 인스턴스
manager = ConnectionManager()


