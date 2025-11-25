"""
Slack Socket Mode 리스너
ZEP로부터 Slack 채널에 전송된 메시지를 실시간으로 감지하고 파싱합니다.
"""
import re
import asyncio
from typing import Optional, Dict, Tuple
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
        
        self.last_event_times: Dict[Tuple[int, str], float] = {}
        self.duplicate_threshold = 0.01
        self.student_cache: Dict[str, int] = {}
        
        self.role_keywords = {"조교", "주강사", "멘토", "매니저"}
        
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
        
        filtered = [part for part in korean_parts if part not in self.role_keywords]
        
        if filtered:
            return filtered[-1]
        elif korean_parts:
            return korean_parts[-1]
        
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
        
        filtered = [part for part in korean_parts if part not in self.role_keywords]
        target_parts = filtered if filtered else korean_parts
        
        return list(reversed(target_parts)) if target_parts else [zep_name.strip()]
    
    def _is_duplicate_event(self, student_id: int, event_type: str, message_ts: float) -> bool:
        """
        중복 이벤트 체크 (0.01초 이내 동일 이벤트만 무시 - 대폭 단축)
        
        Args:
            student_id: 학생 ID
            event_type: 이벤트 타입 ("camera_on", "camera_off", "user_join", "user_leave")
            message_ts: 메시지 타임스탬프
            
        Returns:
            중복이면 True, 아니면 False
        """
        key = (student_id, event_type)
        last_time = self.last_event_times.get(key)
        
        if last_time is None:
            # 첫 이벤트
            self.last_event_times[key] = message_ts
            return False
        
        # 마지막 이벤트와 시간 차이 계산
        time_diff = abs(message_ts - last_time)  # 절대값 사용 (타임스탬프가 역순일 수도 있음)
        
        if time_diff < self.duplicate_threshold:
            return True
        
        self.last_event_times[key] = message_ts
        return False
    
    async def _refresh_student_cache(self):
        """학생 명단을 메모리에 캐싱"""
        try:
            students = await self.db_service.get_all_students()
            self.student_cache = {s.zep_name: s.id for s in students}
        except Exception:
            pass
    
    async def _broadcast_status_change(self, student_id: int, zep_name: str, event_type: str, is_cam_on: bool):
        """브로드캐스트를 비동기로 실행하는 헬퍼 함수"""
        try:
            await manager.broadcast_student_status_changed(
                student_id=student_id,
                zep_name=zep_name,
                event_type=event_type,
                is_cam_on=is_cam_on,
                elapsed_minutes=0
            )
            if self.monitor_service:
                await self.monitor_service.broadcast_dashboard_update_now()
        except Exception:
            pass
    
    def _setup_handlers(self):
        @self.app.event("message")
        async def handle_message(event, say):
            try:
                text = event.get("text", "")
                message_ts_str = event.get("ts", "")
                message_ts = float(message_ts_str) if message_ts_str else 0
                
                asyncio.create_task(self._process_message_async(text, message_ts))
            except Exception:
                pass
    
    async def _process_message_async(self, text: str, message_ts: float):
        """메시지를 비동기로 처리"""
        try:
            if self.monitor_service and self.monitor_service.is_resetting:
                return
            
            current_time = datetime.now().timestamp()
            if message_ts < self.start_time:
                if (current_time - message_ts) > 60:
                    return
            
            message_dt = datetime.fromtimestamp(message_ts, tz=timezone.utc) if message_ts > 0 else None
            
            match_on = self.pattern_cam_on.search(text)
            if match_on:
                zep_name_raw = match_on.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_camera_on(zep_name_raw, zep_name, message_dt, message_ts)
                return
            
            match_off = self.pattern_cam_off.search(text)
            if match_off:
                zep_name_raw = match_off.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_camera_off(zep_name_raw, zep_name, message_dt, message_ts)
                return
            
            match_leave = self.pattern_leave.search(text)
            if match_leave:
                zep_name_raw = match_leave.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_user_leave(zep_name_raw, zep_name, message_dt, message_ts)
                return
            
            match_join = self.pattern_join.search(text)
            if match_join:
                zep_name_raw = match_join.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_user_join(zep_name_raw, zep_name, message_dt, message_ts)
                return
        except Exception:
            pass
    
    async def _handle_camera_on(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0):
        try:
            student_id = None
            matched_name = zep_name
            
            for name in self._extract_all_korean_names(zep_name_raw):
                if name in self.student_cache:
                    student_id = self.student_cache[name]
                    matched_name = name
                    break
            
            if not student_id:
                student = await self.db_service.get_student_by_zep_name(zep_name)
                if student:
                    student_id = student.id
                    matched_name = student.zep_name
                    self.student_cache[matched_name] = student_id
            
            if not student_id:
                return
            
            if self._is_duplicate_event(student_id, "camera_on", message_ts):
                return
            
            await self.db_service.clear_absent_status(student_id)
            success = await self.db_service.update_camera_status(matched_name, True, message_timestamp)
            
            if not success:
                return
            
            if not self.is_restoring:
                asyncio.create_task(self._broadcast_status_change(
                    student_id=student_id,
                    zep_name=matched_name,
                    event_type='camera_on',
                    is_cam_on=True
                ))
        except Exception:
            pass
    
    async def _handle_camera_off(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0):
        try:
            student_id = None
            matched_name = zep_name
            
            for name in self._extract_all_korean_names(zep_name_raw):
                if name in self.student_cache:
                    student_id = self.student_cache[name]
                    matched_name = name
                    break
            
            if not student_id:
                student = await self.db_service.get_student_by_zep_name(zep_name)
                if student:
                    student_id = student.id
                    matched_name = student.zep_name
                    self.student_cache[matched_name] = student_id
            
            if not student_id:
                return
            
            if self._is_duplicate_event(student_id, "camera_off", message_ts):
                return
            
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)
            
            if not success:
                return
            
            if not self.is_restoring:
                asyncio.create_task(self._broadcast_status_change(
                    student_id=student_id,
                    zep_name=matched_name,
                    event_type='camera_off',
                    is_cam_on=False
                ))
        except Exception:
            pass
    
    async def _handle_user_join(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0):
        try:
            student_id = None
            matched_name = zep_name
            
            for name in self._extract_all_korean_names(zep_name_raw):
                if name in self.student_cache:
                    student_id = self.student_cache[name]
                    matched_name = name
                    break
            
            if not student_id:
                student = await self.db_service.get_student_by_zep_name(zep_name)
                if student:
                    student_id = student.id
                    matched_name = student.zep_name
                    self.student_cache[matched_name] = student_id
            
            if not student_id:
                return
            
            if self._is_duplicate_event(student_id, "user_join", message_ts):
                return
            
            self.joined_students_today.add(student_id)
            
            await self.db_service.clear_absent_status(student_id)
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)
            
            if success and not self.is_restoring:
                asyncio.create_task(self._broadcast_status_change(
                    student_id=student_id,
                    zep_name=matched_name,
                    event_type='user_join',
                    is_cam_on=False
                ))
        except Exception:
            pass
    
    async def _handle_user_leave(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0):
        try:
            # ⭐ 1. 캐시에서 학생 찾기 (DB 조회 X)
            student_id = None
            matched_name = zep_name
            korean_names = self._extract_all_korean_names(zep_name_raw)
            
            for name in korean_names:
                if name in self.student_cache:
                    student_id = self.student_cache[name]
                    matched_name = name
                    break
            
            if not student_id:
                student = await self.db_service.get_student_by_zep_name(zep_name)
                if student:
                    student_id = student.id
                    matched_name = student.zep_name
                    self.student_cache[matched_name] = student_id
            
            if not student_id:
                return
            
            if self._is_duplicate_event(student_id, "user_leave", message_ts):
                return
            
            await self.db_service.record_user_leave(student_id)
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)
            
            if success and not self.is_restoring:
                asyncio.create_task(self._broadcast_status_change(
                    student_id=student_id,
                    zep_name=matched_name,
                    event_type='user_leave',
                    is_cam_on=False
                ))
        except Exception:
            pass
    
    async def restore_state_from_history(self, lookback_hours: int = 24):
        try:
            self.is_restoring = True
            self.joined_students_today.clear()
            self.last_event_times.clear()
            
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
                    await self._handle_camera_on(zep_name_raw, zep_name, message_dt, message_ts)
                    continue
                
                match_off = self.pattern_cam_off.search(text)
                if match_off:
                    zep_name_raw = match_off.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    await self._handle_camera_off(zep_name_raw, zep_name, message_dt, message_ts)
                    continue
                
                match_leave = self.pattern_leave.search(text)
                if match_leave:
                    zep_name_raw = match_leave.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    await self._handle_user_leave(zep_name_raw, zep_name, message_dt, message_ts)
                    continue
                
                match_join = self.pattern_join.search(text)
                if match_join:
                    zep_name_raw = match_join.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    await self._handle_user_join(zep_name_raw, zep_name, message_dt, message_ts)
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
            
            await self._refresh_student_cache()
            
            await self.restore_state_from_history(lookback_hours=24)
            await self.handler.start_async()
        except Exception as e:
            raise
    
    async def stop(self):
        if self.handler:
            await self.handler.close_async()
