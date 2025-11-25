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
        
        # ⭐ 학생별 마지막 이벤트 타임스탬프 저장 (중복 방지)
        # key: (student_id, event_type), value: timestamp
        self.last_event_times: Dict[Tuple[int, str], float] = {}
        # [핵심 수정] 0.3초는 너무 길어 빠른 ON/OFF를 무시합니다.
        # 0.01초로 대폭 줄여 진짜 중복만 필터링하도록 수정합니다.
        self.duplicate_threshold = 0.01  # 0.01초 이내 중복 이벤트만 무시 (대폭 단축)
        
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
        
        # ⭐ 0.01초로 단축 (너무 짧은 간격의 진짜 중복만 필터링)
        if time_diff < self.duplicate_threshold:
            # 0.01초 이내 중복 이벤트 (진짜 중복만 필터링)
            # [수정] 로그에 임계값 정보를 추가하여 디버깅이 쉽도록 개선
            print(f"    ⏭️ 중복 무시: {event_type} (ID: {student_id}, {time_diff:.3f}초 < {self.duplicate_threshold}초)", flush=True)
            return True
        
        # 중복 아님 - 타임스탬프 업데이트
        self.last_event_times[key] = message_ts
        return False
    
    async def _broadcast_status_change(self, student_id: int, zep_name: str, event_type: str, is_cam_on: bool):
        """브로드캐스트를 비동기로 실행하는 헬퍼 함수 (블로킹 방지)"""
        try:
            # ⭐ 학생 상태 변경만 즉시 브로드캐스트 (가벼운 작업)
            await manager.broadcast_student_status_changed(
                student_id=student_id,
                zep_name=zep_name,
                event_type=event_type,
                is_cam_on=is_cam_on,
                elapsed_minutes=0
            )
            # ⭐ 대시보드 업데이트 제거 (성능 저하 원인)
            # - 주기적 업데이트(5초마다)가 이미 있음
            # - 매 상태 변경마다 전체 학생 조회는 불필요하고 블로킹 발생
            # - 프론트엔드 추가 전에는 이런 브로드캐스트가 없었음
        except Exception as e:
            print(f"    ❌ 브로드캐스트 오류: {e}", flush=True)
    
    def _setup_handlers(self):
        @self.app.event("message")
        async def handle_message(event, say):
            # ⭐ 메시지 수신 즉시 반환 (블로킹 방지)
            # 실제 처리는 비동기 태스크로 실행
            try:
                text = event.get("text", "")
                message_ts_str = event.get("ts", "")
                message_ts = float(message_ts_str) if message_ts_str else 0
                
                # 메시지 수신 로그 (즉시 출력)
                print(f"🔍 [Slack] {text[:50]}...", flush=True)
                
                # 비동기 태스크로 처리 (블로킹 없이 즉시 반환)
                asyncio.create_task(self._process_message_async(text, message_ts))
            except Exception as e:
                print(f"    ❌ 메시지 수신 오류: {e}", flush=True)
    
    async def _process_message_async(self, text: str, message_ts: float):
        """메시지를 비동기로 처리 (블로킹 없음)"""
        try:
            if self.monitor_service and self.monitor_service.is_resetting:
                return
            
            # ⭐ 프로그램 시작 이전 메시지는 무시하되, 최근 1분 이내는 처리
            current_time = datetime.now().timestamp()
            if message_ts < self.start_time:
                # 1분(60초) 이내 메시지는 처리 (프로그램 재시작 직후 놓친 메시지 처리)
                if (current_time - message_ts) > 60:
                    return
            
            # 메시지 타임스탬프를 datetime으로 변환
            message_dt = datetime.fromtimestamp(message_ts, tz=timezone.utc) if message_ts > 0 else None
            
            match_on = self.pattern_cam_on.search(text)
            if match_on:
                zep_name_raw = match_on.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                print(f"    ✅ ON: {zep_name_raw} → {zep_name}", flush=True)
                await self._handle_camera_on(zep_name_raw, zep_name, message_dt, message_ts)
                return
            
            match_off = self.pattern_cam_off.search(text)
            if match_off:
                zep_name_raw = match_off.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                print(f"    ✅ OFF: {zep_name_raw} → {zep_name}", flush=True)
                await self._handle_camera_off(zep_name_raw, zep_name, message_dt, message_ts)
                return
            
            match_leave = self.pattern_leave.search(text)
            if match_leave:
                zep_name_raw = match_leave.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                print(f"    ✅ 퇴장: {zep_name_raw} → {zep_name}", flush=True)
                await self._handle_user_leave(zep_name_raw, zep_name, message_dt, message_ts)
                return
            
            match_join = self.pattern_join.search(text)
            if match_join:
                zep_name_raw = match_join.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                print(f"    ✅ 입장: {zep_name_raw} → {zep_name}", flush=True)
                await self._handle_user_join(zep_name_raw, zep_name, message_dt, message_ts)
                return
        except Exception as e:
            # 예외 발생 시 로그 출력 (누락 방지)
            print(f"    ❌ 메시지 처리 오류: {e}", flush=True)
            import traceback
            traceback.print_exc()
    
    async def _handle_camera_on(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0):
        try:
            student = None
            matched_name = zep_name
            for name in self._extract_all_korean_names(zep_name_raw):
                student = await self.db_service.get_student_by_zep_name(name)
                if student:
                    matched_name = name
                    break
            
            if not student:
                return
            
            # ⭐ 중복 이벤트 체크
            if self._is_duplicate_event(student.id, "camera_on", message_ts):
                return
            
            if student.is_absent:
                await self.db_service.clear_absent_status(student.id)
            
            # DB 업데이트
            success = await self.db_service.update_camera_status(matched_name, True, message_timestamp)
            
            if not success:
                return
            
            # ⭐ 성공 시 항상 브로드캐스트 (DB 재조회 제거 - student 객체 직접 사용)
            if not self.is_restoring:
                # student 객체의 상태를 직접 업데이트해서 사용 (DB 재조회 불필요)
                student.is_cam_on = True
                
                # 브로드캐스트를 비동기 태스크로 실행 (블로킹 방지)
                asyncio.create_task(self._broadcast_status_change(
                    student_id=student.id,
                    zep_name=student.zep_name,
                    event_type='camera_on',
                    is_cam_on=True
                ))
        except Exception as e:
            print(f"    ❌ 카메라 ON 처리 오류: {e}", flush=True)
    
    async def _handle_camera_off(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0):
        try:
            student = None
            matched_name = zep_name
            for name in self._extract_all_korean_names(zep_name_raw):
                student = await self.db_service.get_student_by_zep_name(name)
                if student:
                    matched_name = name
                    break
            
            if not student:
                return
            
            # ⭐ 중복 이벤트 체크
            if self._is_duplicate_event(student.id, "camera_off", message_ts):
                return
            
            # DB 업데이트
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)
            
            if not success:
                return
            
            # ⭐ 성공 시 항상 브로드캐스트 (DB 재조회 제거 - student 객체 직접 사용)
            if not self.is_restoring:
                # student 객체의 상태를 직접 업데이트해서 사용 (DB 재조회 불필요)
                student.is_cam_on = False
                
                # 브로드캐스트를 비동기 태스크로 실행 (블로킹 방지)
                asyncio.create_task(self._broadcast_status_change(
                    student_id=student.id,
                    zep_name=student.zep_name,
                    event_type='camera_off',
                    is_cam_on=False
                ))
        except Exception as e:
            print(f"    ❌ 카메라 OFF 처리 오류: {e}", flush=True)
    
    async def _handle_user_join(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0):
        try:
            student = None
            matched_name = zep_name
            for name in self._extract_all_korean_names(zep_name_raw):
                student = await self.db_service.get_student_by_zep_name(name)
                if student:
                    matched_name = name
                    break
            
            if not student:
                return
            
            # ⭐ 중복 이벤트 체크
            if self._is_duplicate_event(student.id, "user_join", message_ts):
                return
            
            self.joined_students_today.add(student.id)
            
            if student.is_absent:
                await self.db_service.clear_absent_status(student.id)
            
            await self.db_service.clear_absent_status(student.id)
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)
            
            if success and not self.is_restoring:
                # student 객체의 상태를 직접 업데이트해서 사용 (DB 재조회 불필요)
                student.is_cam_on = False
                
                # 브로드캐스트를 비동기 태스크로 실행 (블로킹 방지)
                asyncio.create_task(self._broadcast_status_change(
                    student_id=student.id,
                    zep_name=student.zep_name,
                    event_type='user_join',
                    is_cam_on=False
                ))
        except Exception as e:
            print(f"    ❌ 입장 처리 오류: {e}", flush=True)
    
    async def _handle_user_leave(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0):
        try:
            student = None
            matched_name = zep_name
            korean_names = self._extract_all_korean_names(zep_name_raw)
            
            for name in korean_names:
                student = await self.db_service.get_student_by_zep_name(name)
                if student:
                    matched_name = name
                    break
            
            if not student:
                return
            
            # ⭐ 중복 이벤트 체크
            if self._is_duplicate_event(student.id, "user_leave", message_ts):
                return
            
            await self.db_service.record_user_leave(student.id)
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)
            
            if success and not self.is_restoring:
                # student 객체의 상태를 직접 업데이트해서 사용 (DB 재조회 불필요)
                student.is_cam_on = False
                
                # 브로드캐스트를 비동기 태스크로 실행 (블로킹 방지)
                asyncio.create_task(self._broadcast_status_change(
                    student_id=student.id,
                    zep_name=student.zep_name,
                    event_type='user_leave',
                    is_cam_on=False
                ))
        except Exception as e:
            print(f"    ❌ 퇴장 처리 오류: {e}", flush=True)
    
    async def restore_state_from_history(self, lookback_hours: int = 24):
        try:
            self.is_restoring = True
            self.joined_students_today.clear()
            # ⭐ 히스토리 복원 시 이벤트 타임스탬프도 초기화
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
            
            await self.restore_state_from_history(lookback_hours=24)
            await self.handler.start_async()
        except Exception as e:
            raise
    
    async def stop(self):
        if self.handler:
            await self.handler.close_async()
