"""
Slack Socket Mode 리스너
ZEP로부터 Slack 채널에 전송된 메시지를 실시간으로 감지하고 파싱합니다.
"""
import re
from typing import Optional
from datetime import datetime, timedelta, timezone
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from config import config
from database import DBService
from api.websocket_manager import manager


class SlackListener:
    def __init__(self, monitor_service=None):
        self.app = AsyncApp(token=config.SLACK_BOT_TOKEN)
        self.handler = None
        self.db_service = DBService()
        self.monitor_service = monitor_service
        self.start_time = datetime.now().timestamp()
        self.is_restoring = False
        self.joined_students_today = set()
        
        self.pattern_cam_on = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님(?:의|이)?\s*카메라(?:를|가)\s*(?:켰습니다|on\s*되었습니다)")
        self.pattern_cam_off = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님(?:의|이)?\s*카메라(?:를|가)\s*(?:껐습니다|off\s*되었습니다)")
        self.pattern_leave = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님이?\s*.*(퇴장|접속\s*종료|접속을\s*종료|나갔습니다)(?:했습니다)?")
        self.pattern_join = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님이?\s*.*(입장|접속했습니다|들어왔습니다)")
        
        self._setup_handlers()
    
    def _extract_name_only(self, zep_name: str) -> str:
        parts = re.split(r'[/_\-|\s]+', zep_name.strip())
        parts = [part.strip() for part in parts if part.strip()]
        
        korean_parts = []
        for part in parts:
            if any('\uAC00' <= char <= '\uD7A3' for char in part):
                korean_parts.append(part)
        
        if len(korean_parts) > 1:
            return korean_parts[-1]
        elif len(korean_parts) == 1:
            return korean_parts[0]
        
        if parts:
            return parts[0]
        
        return zep_name.strip()
    
    def _extract_all_korean_names(self, zep_name: str) -> list:
        parts = re.split(r'[/_\-|\s]+', zep_name.strip())
        parts = [part.strip() for part in parts if part.strip()]
        
        korean_parts = []
        for part in parts:
            if any('\uAC00' <= char <= '\uD7A3' for char in part):
                korean_parts.append(part)
        
        return list(reversed(korean_parts)) if korean_parts else [zep_name.strip()]
    
    def _setup_handlers(self):
        @self.app.event("message")
        async def handle_message(event, say):
            if self.monitor_service and self.monitor_service.is_resetting:
                return
            
            message_ts = float(event.get("ts", 0))
            if message_ts < self.start_time:
                return
            
            # 메시지 타임스탬프를 datetime으로 변환
            message_dt = datetime.fromtimestamp(message_ts, tz=timezone.utc) if message_ts > 0 else None
            
            text = event.get("text", "")
            
            match_on = self.pattern_cam_on.search(text)
            if match_on:
                zep_name_raw = match_on.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_camera_on(zep_name_raw, zep_name, message_dt)
                return
            
            match_off = self.pattern_cam_off.search(text)
            if match_off:
                zep_name_raw = match_off.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_camera_off(zep_name_raw, zep_name, message_dt)
                return
            
            match_leave = self.pattern_leave.search(text)
            if match_leave:
                zep_name_raw = match_leave.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_user_leave(zep_name_raw, zep_name, message_dt)
                return
            
            match_join = self.pattern_join.search(text)
            if match_join:
                zep_name_raw = match_join.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_user_join(zep_name_raw, zep_name, message_dt)
                return
    
    async def _handle_camera_on(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None):
        student = None
        matched_name = zep_name
        for name in self._extract_all_korean_names(zep_name_raw):
            student = await self.db_service.get_student_by_zep_name(name)
            if student:
                matched_name = name
                break
        
        if student:
            if student.is_absent:
                await self.db_service.clear_absent_status(student.id)
            
            # 상태가 실제로 변경되었는지 확인
            was_cam_on = student.is_cam_on
            success = await self.db_service.update_camera_status(matched_name, True, message_timestamp)
            
            # 상태가 변경되었을 때만 브로드캐스트 (카메라가 꺼져있었는데 켜진 경우)
            if success and not self.is_restoring and not was_cam_on:
                await manager.broadcast_student_status_changed(
                    student_id=student.id,
                    zep_name=student.zep_name,
                    event_type='camera_on',
                    is_cam_on=True,
                    elapsed_minutes=0
                )
                if self.monitor_service:
                    await self.monitor_service.broadcast_dashboard_update_now()
    
    async def _handle_camera_off(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None):
        student = None
        matched_name = zep_name
        for name in self._extract_all_korean_names(zep_name_raw):
            student = await self.db_service.get_student_by_zep_name(name)
            if student:
                matched_name = name
                break
        
        if student:
            # 상태가 실제로 변경되었는지 확인
            was_cam_on = student.is_cam_on
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)
            
            # 상태가 변경되었을 때만 브로드캐스트 (카메라가 켜져있었는데 꺼진 경우)
            if success and not self.is_restoring and was_cam_on:
                await manager.broadcast_student_status_changed(
                    student_id=student.id,
                    zep_name=student.zep_name,
                    event_type='camera_off',
                    is_cam_on=False,
                    elapsed_minutes=0
                )
                if self.monitor_service:
                    await self.monitor_service.broadcast_dashboard_update_now()
    
    async def _handle_user_join(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None):
        student = None
        matched_name = zep_name
        for name in self._extract_all_korean_names(zep_name_raw):
            student = await self.db_service.get_student_by_zep_name(name)
            if student:
                matched_name = name
                break
        
        if student:
            self.joined_students_today.add(student.id)
            
            if student.is_absent:
                await self.db_service.clear_absent_status(student.id)
            
            await self.db_service.clear_absent_status(student.id)
            await self.db_service.update_camera_status(matched_name, False, message_timestamp)
            if not self.is_restoring:
                await manager.broadcast_student_status_changed(
                    student_id=student.id,
                    zep_name=student.zep_name,
                    event_type='user_join',
                    is_cam_on=False,
                    elapsed_minutes=0
                )
                if self.monitor_service:
                    await self.monitor_service.broadcast_dashboard_update_now()
    
    async def _handle_user_leave(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None):
        student = None
        matched_name = zep_name
        korean_names = self._extract_all_korean_names(zep_name_raw)
        
        for name in korean_names:
            student = await self.db_service.get_student_by_zep_name(name)
            if student:
                matched_name = name
                break
        
        if student:
            await self.db_service.record_user_leave(student.id)
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)
            if success and not self.is_restoring:
                await manager.broadcast_student_status_changed(
                    student_id=student.id,
                    zep_name=student.zep_name,
                    event_type='user_leave',
                    is_cam_on=False,
                    elapsed_minutes=0
                )
                if self.monitor_service:
                    await self.monitor_service.broadcast_dashboard_update_now()
    
    async def restore_state_from_history(self, lookback_hours: int = 24):
        try:
            self.is_restoring = True
            self.joined_students_today.clear()
            await self.db_service.reset_all_camera_status()
            
            now = datetime.now()
            
            if config.DAILY_RESET_TIME:
                from datetime import time as time_type
                try:
                    reset_time = datetime.strptime(config.DAILY_RESET_TIME, "%H:%M").time()
                    today_reset = datetime.combine(now.date(), reset_time)
                    
                    if now < today_reset:
                        oldest_dt = today_reset - timedelta(days=1)
                    else:
                        oldest_dt = today_reset
                except ValueError:
                    oldest_dt = datetime.combine(now.date(), time_type(0, 0))
            else:
                oldest_dt = datetime.combine(now.date(), datetime.min.time())
            
            oldest_ts = oldest_dt.timestamp()
            
            messages = []
            cursor = None
            
            while True:
                response = await self.app.client.conversations_history(
                    channel=config.SLACK_CHANNEL_ID,
                    oldest=str(oldest_ts),
                    limit=1000,
                    cursor=cursor
                )
                
                batch = response.get("messages", [])
                messages.extend(batch)
                
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
            
            if not messages:
                return
            
            messages.sort(key=lambda msg: float(msg.get("ts", 0)))
            
            for message in messages:
                text = message.get("text", "")
                message_ts = float(message.get("ts", 0))
                message_dt = datetime.fromtimestamp(message_ts, tz=timezone.utc) if message_ts > 0 else None
                
                match_on = self.pattern_cam_on.search(text)
                if match_on:
                    zep_name_raw = match_on.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    await self._handle_camera_on(zep_name_raw, zep_name, message_dt)
                    continue
                
                match_off = self.pattern_cam_off.search(text)
                if match_off:
                    zep_name_raw = match_off.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    await self._handle_camera_off(zep_name_raw, zep_name, message_dt)
                    continue
                
                match_leave = self.pattern_leave.search(text)
                if match_leave:
                    zep_name_raw = match_leave.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    await self._handle_user_leave(zep_name_raw, zep_name, message_dt)
                    continue
                
                match_join = self.pattern_join.search(text)
                if match_join:
                    zep_name_raw = match_join.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    await self._handle_user_join(zep_name_raw, zep_name, message_dt)
                    continue
            
            await self.db_service.reset_all_alert_fields()
            
        except Exception:
            pass
        finally:
            self.is_restoring = False
    
    def get_joined_students_today(self) -> set:
        return self.joined_students_today
    
    async def start(self):
        try:
            self.handler = AsyncSocketModeHandler(
                self.app,
                config.SLACK_APP_TOKEN
            )
            
            await self.restore_state_from_history(lookback_hours=24)
            await self.handler.start_async()
        except Exception as e:
            raise
    
    async def stop(self):
        if self.handler:
            await self.handler.close_async()
