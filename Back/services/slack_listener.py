"""
Slack Socket Mode 리스너
ZEP로부터 Slack 채널에 전송된 메시지를 실시간으로 감지하고 파싱합니다.
"""
import re
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from datetime import datetime, timedelta, timezone
from asyncio import Queue
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from config import config
from database import DBService
from api.websocket_manager import manager

logger = logging.getLogger(__name__)


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

        # 초기화 중 이벤트 큐
        self.pending_events: Queue = Queue()
        self.processing_pending = False
        
        self.role_keywords = {
            "조교", "주강사", "멘토", "매니저",
            "개발자", "학생", "수강생", "교육생",
            "강사", "관리자", "운영자", "팀장",
            "강의", "실습", "프로젝트", "팀"
        }
        self.ignore_keywords: List[str] = self._load_ignore_keywords()
        
        self.pattern_cam_on = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님(?:의|이)?\s*카메라(?:를|가)\s*(?:켰습니다|on\s*되었습니다)")
        self.pattern_cam_off = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님(?:의|이)?\s*카메라(?:를|가)\s*(?:껐습니다|off\s*되었습니다)")
        self.pattern_leave = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님이?\s*.*(퇴장|접속\s*종료|접속을\s*종료|나갔습니다)(?:했습니다)?")
        self.pattern_join = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님이?\s*.*(입장|접속했습니다|들어왔습니다)")
        
        self._setup_handlers()
    
    def _load_ignore_keywords(self) -> List[str]:
        """설정 파일에서 무시할 키워드 목록 로드"""
        settings_file = Path(__file__).parent.parent / "data" / "settings.json"
        default_keywords = ["test", "monitor", "debug", "temp"]
        
        if not settings_file.exists():
            return default_keywords
        
        try:
            data = json.loads(settings_file.read_text(encoding="utf-8"))
            keywords = data.get("ignore_keywords", default_keywords)
            if isinstance(keywords, list):
                return [str(kw).lower() for kw in keywords if kw]
            return default_keywords
        except Exception:
            return default_keywords
    
    def _should_ignore_name(self, zep_name: str) -> bool:
        """
        특정 키워드가 포함된 이름인지 확인
        구분자(_, -, ., 공백, 괄호)로 분리하여 키워드 체크
        """
        if not zep_name or not self.ignore_keywords:
            return False
        
        # 구분자로 분리: _, -, ., 공백, 괄호 등
        parts = re.split(r'[/_\-.\s()]+', zep_name.lower())
        
        # 분리된 부분 중 하나라도 키워드와 일치하면 무시
        for part in parts:
            if part and part in [kw.lower() for kw in self.ignore_keywords]:
                return True
        
        return False
    
    def _extract_name_only(self, zep_name: str) -> str:
        """ZEP 이름에서 실제 이름만 추출"""
        if not zep_name:  # None 또는 빈 문자열 체크
            return ""

        # 구분자 확대: /_-|공백 + .()@{}[]
        parts = re.split(r'[/_\-|\s.()@{}\[\]]+', zep_name.strip())
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
        """ZEP 이름에서 모든 한글 이름 추출 (역순)"""
        if not zep_name:  # None 또는 빈 문자열 체크
            return []

        # 구분자 확대: /_-|공백 + .()@{}[]
        parts = re.split(r'[/_\-|\s.()@{}\[\]]+', zep_name.strip())
        parts = [part.strip() for part in parts if part.strip()]

        korean_parts = []
        for part in parts:
            if any('\uAC00' <= char <= '\uD7A3' for char in part):
                korean_parts.append(part)

        filtered = [part for part in korean_parts if part not in self.role_keywords]
        target_parts = filtered if filtered else korean_parts

        return list(reversed(target_parts)) if target_parts else [zep_name.strip()]
    
    def _is_duplicate_event(self, student_id: int, event_type: str, message_ts: float) -> bool:
        """중복 이벤트 체크 (0.01초 이내 동일 이벤트만 무시)"""
        key = (student_id, event_type)
        last_time = self.last_event_times.get(key)
        
        if last_time is None:
            self.last_event_times[key] = message_ts
            return False
        
        time_diff = abs(message_ts - last_time)
        
        if time_diff < self.duplicate_threshold:
            return True
        
        self.last_event_times[key] = message_ts
        return False
    
    async def _refresh_student_cache(self):
        """학생 명단을 메모리에 캐싱 (이름 변형도 포함)"""
        try:
            students = await self.db_service.get_all_students()
            self.student_cache = {}
            
            for student in students:
                self.student_cache[student.zep_name] = student.id
                korean_names = self._extract_all_korean_names(student.zep_name)
                for korean_name in korean_names:
                    if korean_name not in self.student_cache:
                        self.student_cache[korean_name] = student.id
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
            # 동기화 중에는 실시간 이벤트 처리 중지 (동기화 결과를 덮어쓰지 않기 위해)
            if self.is_restoring:
                return

            # 초기화 중이면 이벤트를 큐에 저장
            if self.monitor_service and self.monitor_service.is_resetting:
                await self.pending_events.put({
                    'text': text,
                    'message_ts': message_ts
                })
                logger.debug(f"[초기화 중] 이벤트 큐잉: {text[:50]}")
                return
            
            current_time = datetime.now().timestamp()
            if message_ts < self.start_time:
                if (current_time - message_ts) > 60:
                    return
            
            message_dt = datetime.fromtimestamp(message_ts, tz=timezone.utc) if message_ts > 0 else None
            
            match_on = self.pattern_cam_on.search(text)
            if match_on:
                zep_name_raw = match_on.group(1)
                if self._should_ignore_name(zep_name_raw):
                    return
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_camera_on(zep_name_raw, zep_name, message_dt, message_ts)
                return
            
            match_off = self.pattern_cam_off.search(text)
            if match_off:
                zep_name_raw = match_off.group(1)
                if self._should_ignore_name(zep_name_raw):
                    return
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_camera_off(zep_name_raw, zep_name, message_dt, message_ts)
                return
            
            match_leave = self.pattern_leave.search(text)
            if match_leave:
                zep_name_raw = match_leave.group(1)
                if self._should_ignore_name(zep_name_raw):
                    return
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_user_leave(zep_name_raw, zep_name, message_dt, message_ts)
                return
            
            match_join = self.pattern_join.search(text)
            if match_join:
                zep_name_raw = match_join.group(1)
                if self._should_ignore_name(zep_name_raw):
                    return
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_user_join(zep_name_raw, zep_name, message_dt, message_ts)
                return
        except Exception:
            pass
    
    async def _handle_camera_on(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0, add_to_joined_today: bool = True):
        try:
            student_id = None
            matched_name = zep_name

            for name in self._extract_all_korean_names(zep_name_raw):
                if name in self.student_cache:
                    student_id = self.student_cache[name]
                    student = await self.db_service.get_student_by_id(student_id)
                    if student:
                        matched_name = student.zep_name
                    break

            if not student_id:
                student = await self.db_service.get_student_by_zep_name(zep_name_raw)
                if not student:
                    for name in self._extract_all_korean_names(zep_name_raw):
                        student = await self.db_service.get_student_by_zep_name(name)
                        if student:
                            break

                if student:
                    student_id = student.id
                    matched_name = student.zep_name
                    self.student_cache[matched_name] = student_id
                    for name in self._extract_all_korean_names(zep_name_raw):
                        if name not in self.student_cache:
                            self.student_cache[name] = student_id

            if not student_id:
                logger.warning(f"[매칭 실패 - 카메라 ON] ZEP 이름: '{zep_name_raw}'")
                logger.debug(f"  - 추출된 이름들: {self._extract_all_korean_names(zep_name_raw)}")
                return

            if self._is_duplicate_event(student_id, "camera_on", message_ts):
                return

            if add_to_joined_today:
                self.joined_students_today.add(student_id)
            await self.db_service.clear_absent_status(student_id)
            success = await self.db_service.update_camera_status(matched_name, True, message_timestamp)

            if not success:
                return

            # 상태 변경 로그
            timestamp_str = message_timestamp.strftime("%H:%M:%S") if message_timestamp else "N/A"
            logger.info(f"[카메라 ON] {matched_name} | 시각: {timestamp_str}")

            if not self.is_restoring:
                asyncio.create_task(self._broadcast_status_change(
                    student_id=student_id,
                    zep_name=matched_name,
                    event_type='camera_on',
                    is_cam_on=True
                ))
        except Exception as e:
            logger.error(f"[카메라 ON 처리 실패] ZEP: {zep_name_raw}, 오류: {e}", exc_info=True)
    
    async def _handle_camera_off(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0, add_to_joined_today: bool = True):
        try:
            student_id = None
            matched_name = zep_name
            
            for name in self._extract_all_korean_names(zep_name_raw):
                if name in self.student_cache:
                    student_id = self.student_cache[name]
                    student = await self.db_service.get_student_by_id(student_id)
                    if student:
                        matched_name = student.zep_name
                    break
            
            if not student_id:
                student = await self.db_service.get_student_by_zep_name(zep_name_raw)
                if not student:
                    for name in self._extract_all_korean_names(zep_name_raw):
                        student = await self.db_service.get_student_by_zep_name(name)
                        if student:
                            break
                
                if student:
                    student_id = student.id
                    matched_name = student.zep_name
                    self.student_cache[matched_name] = student_id
                    for name in self._extract_all_korean_names(zep_name_raw):
                        if name not in self.student_cache:
                            self.student_cache[name] = student_id

            if not student_id:
                logger.warning(f"[매칭 실패 - 카메라 OFF] ZEP 이름: '{zep_name_raw}'")
                logger.debug(f"  - 추출된 이름들: {self._extract_all_korean_names(zep_name_raw)}")
                return

            if self._is_duplicate_event(student_id, "camera_off", message_ts):
                return
            
            if add_to_joined_today:
                self.joined_students_today.add(student_id)
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)

            if not success:
                return

            # 상태 변경 로그
            timestamp_str = message_timestamp.strftime("%H:%M:%S") if message_timestamp else "N/A"
            logger.info(f"[카메라 OFF] {matched_name} | 시각: {timestamp_str}")

            if not self.is_restoring:
                asyncio.create_task(self._broadcast_status_change(
                    student_id=student_id,
                    zep_name=matched_name,
                    event_type='camera_off',
                    is_cam_on=False
                ))
        except Exception as e:
            logger.error(f"[카메라 OFF 처리 실패] ZEP: {zep_name_raw}, 오류: {e}", exc_info=True)
    
    async def _handle_user_join(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0, add_to_joined_today: bool = True):
        try:
            student_id = None
            matched_name = zep_name
            
            for name in self._extract_all_korean_names(zep_name_raw):
                if name in self.student_cache:
                    student_id = self.student_cache[name]
                    student = await self.db_service.get_student_by_id(student_id)
                    if student:
                        matched_name = student.zep_name
                    break
            
            if not student_id:
                student = await self.db_service.get_student_by_zep_name(zep_name_raw)
                if not student:
                    for name in self._extract_all_korean_names(zep_name_raw):
                        student = await self.db_service.get_student_by_zep_name(name)
                        if student:
                            break
                
                if student:
                    student_id = student.id
                    matched_name = student.zep_name
                    self.student_cache[matched_name] = student_id
                    for name in self._extract_all_korean_names(zep_name_raw):
                        if name not in self.student_cache:
                            self.student_cache[name] = student_id

            if not student_id:
                logger.warning(f"[매칭 실패 - 입장] ZEP 이름: '{zep_name_raw}'")
                logger.debug(f"  - 추출된 이름들: {self._extract_all_korean_names(zep_name_raw)}")
                return

            if self._is_duplicate_event(student_id, "user_join", message_ts):
                return
            
            if add_to_joined_today:
                self.joined_students_today.add(student_id)

            await self.db_service.clear_absent_status(student_id)
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)

            # 상태 변경 로그
            if success:
                timestamp_str = message_timestamp.strftime("%H:%M:%S") if message_timestamp else "N/A"
                logger.info(f"[입장] {matched_name} | 시각: {timestamp_str}")

            if success and not self.is_restoring:
                asyncio.create_task(self._broadcast_status_change(
                    student_id=student_id,
                    zep_name=matched_name,
                    event_type='user_join',
                    is_cam_on=False
                ))
        except Exception as e:
            logger.error(f"[입장 처리 실패] ZEP: {zep_name_raw}, 오류: {e}", exc_info=True)
    
    async def _handle_user_leave(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0):
        try:
            student_id = None
            matched_name = zep_name
            korean_names = self._extract_all_korean_names(zep_name_raw)
            
            # 1. 캐시에서 찾기 (한글 이름 부분 포함)
            for name in korean_names:
                if name in self.student_cache:
                    student_id = self.student_cache[name]
                    # 실제 DB 이름 찾기
                    student = await self.db_service.get_student_by_id(student_id)
                    if student:
                        matched_name = student.zep_name
                    break
            
            # 2. 캐시에 없으면 DB에서 부분 일치로 찾기
            if not student_id:
                student = await self.db_service.get_student_by_zep_name(zep_name_raw)
                if not student:
                    # 한글 이름 부분으로도 시도
                    for name in korean_names:
                        student = await self.db_service.get_student_by_zep_name(name)
                        if student:
                            break
                
                if student:
                    student_id = student.id
                    matched_name = student.zep_name
                    # 캐시에 추가 (원본 이름과 한글 이름 모두)
                    self.student_cache[matched_name] = student_id
                    for name in korean_names:
                        if name not in self.student_cache:
                            self.student_cache[name] = student_id

            if not student_id:
                logger.warning(f"[매칭 실패 - 퇴장] ZEP 이름: '{zep_name_raw}'")
                logger.debug(f"  - 추출된 이름들: {self._extract_all_korean_names(zep_name_raw)}")
                return

            if self._is_duplicate_event(student_id, "user_leave", message_ts):
                return

            await self.db_service.record_user_leave(student_id)
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)

            # 상태 변경 로그
            if success:
                timestamp_str = message_timestamp.strftime("%H:%M:%S") if message_timestamp else "N/A"
                logger.info(f"[퇴장] {matched_name} | 시각: {timestamp_str}")

            if success and not self.is_restoring:
                asyncio.create_task(self._broadcast_status_change(
                    student_id=student_id,
                    zep_name=matched_name,
                    event_type='user_leave',
                    is_cam_on=False
                ))
        except Exception as e:
            logger.error(f"[퇴장 처리 실패] ZEP: {zep_name_raw}, 오류: {e}", exc_info=True)

    async def process_pending_events(self):
        """초기화 완료 후 대기 중인 이벤트 처리"""
        if self.processing_pending:
            return

        self.processing_pending = True
        count = self.pending_events.qsize()

        if count > 0:
            logger.info(f"[큐 처리 시작] {count}개 이벤트 처리")

        try:
            while not self.pending_events.empty():
                event = await self.pending_events.get()
                await self._process_message_async(**event)
        finally:
            self.processing_pending = False
            if count > 0:
                logger.info(f"[큐 처리 완료]")

    async def restore_state_from_history(self, lookback_hours: int = 24):
        try:
            self.is_restoring = True
            self.joined_students_today.clear()
            self.last_event_times.clear()
            
            await self._refresh_student_cache()
            
            # monitor_service의 reset_time 사용 (UTC 기준)
            now_utc = datetime.now(timezone.utc)
            now_local = datetime.now()
            
            if self.monitor_service and self.monitor_service.reset_time:
                # monitor_service의 reset_time 사용 (이미 UTC)
                reset_time_utc = self.monitor_service.reset_time
                today_reset_ts = reset_time_utc.timestamp()
                # 24시간 전부터 조회
                oldest_dt = reset_time_utc - timedelta(hours=24)
                oldest_ts = oldest_dt.timestamp()
            elif config.DAILY_RESET_TIME:
                from datetime import time as time_type
                try:
                    reset_time = datetime.strptime(config.DAILY_RESET_TIME, "%H:%M").time()
                    today_reset_local = datetime.combine(now_local.date(), reset_time)
                    
                    if now_local < today_reset_local:
                        today_reset_local = today_reset_local - timedelta(days=1)
                    
                    # UTC로 변환
                    today_reset_utc = today_reset_local.replace(tzinfo=timezone.utc)
                    today_reset_ts = today_reset_utc.timestamp()
                    oldest_dt = today_reset_utc - timedelta(hours=24)
                    oldest_ts = oldest_dt.timestamp()
                except ValueError:
                    oldest_dt_local = datetime.combine(now_local.date(), time_type(0, 0))
                    oldest_dt = oldest_dt_local.replace(tzinfo=timezone.utc)
                    today_reset_ts = oldest_dt.timestamp()
                    oldest_ts = oldest_dt.timestamp()
            else:
                oldest_dt_local = datetime.combine(now_local.date(), datetime.min.time())
                oldest_dt = oldest_dt_local.replace(tzinfo=timezone.utc)
                today_reset_ts = oldest_dt.timestamp()
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
                
                if not response.get("ok"):
                    error = response.get("error", "unknown_error")
                    print(f"   ⚠️ Slack 채널 조회 실패: {error}")
                    if error == "channel_not_found":
                        print(f"   💡 해결 방법:")
                        print(f"      1. Bot을 채널에 초대했는지 확인")
                        print(f"      2. 채널 ID가 올바른지 확인 (현재: {config.SLACK_CHANNEL_ID})")
                        print(f"      3. Private 채널인 경우 Bot이 초대되어야 합니다")
                    break
                
                batch = response.get("messages", [])
                messages.extend(batch)
                
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
            
            if not messages:
                return
            
            messages.sort(key=lambda msg: float(msg.get("ts", 0)))
            
            processed_count = 0
            camera_on_count = 0
            camera_off_count = 0
            join_count = 0
            leave_count = 0
            
            for message in messages:
                text = message.get("text", "")
                message_ts = float(message.get("ts", 0))
                message_dt = datetime.fromtimestamp(message_ts, tz=timezone.utc) if message_ts > 0 else None
                
                match_on = self.pattern_cam_on.search(text)
                if match_on:
                    zep_name_raw = match_on.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    add_to_joined = message_ts >= today_reset_ts
                    await self._handle_camera_on(zep_name_raw, zep_name, message_dt, message_ts, add_to_joined_today=add_to_joined)
                    camera_on_count += 1
                    processed_count += 1
                    continue
                
                match_off = self.pattern_cam_off.search(text)
                if match_off:
                    zep_name_raw = match_off.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    add_to_joined = message_ts >= today_reset_ts
                    await self._handle_camera_off(zep_name_raw, zep_name, message_dt, message_ts, add_to_joined_today=add_to_joined)
                    camera_off_count += 1
                    processed_count += 1
                    continue
                
                match_leave = self.pattern_leave.search(text)
                if match_leave:
                    zep_name_raw = match_leave.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    await self._handle_user_leave(zep_name_raw, zep_name, message_dt, message_ts)
                    leave_count += 1
                    processed_count += 1
                    continue
                
                match_join = self.pattern_join.search(text)
                if match_join:
                    zep_name_raw = match_join.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    if message_ts >= today_reset_ts:
                        await self._handle_user_join(zep_name_raw, zep_name, message_dt, message_ts)
                        join_count += 1
                    else:
                        await self._handle_user_join(zep_name_raw, zep_name, message_dt, message_ts, add_to_joined_today=False)
                    processed_count += 1
                    continue
            
            await self.db_service.reset_all_alert_fields()
            
            # joined_students_today 복원: DB의 last_status_change를 기준으로 오늘 접속한 학생 추가
            all_students = await self.db_service.get_all_students()

            # 서울 시간 기준 오늘 날짜
            from database.db_service import now_seoul, SEOUL_TZ
            now_seoul_tz = now_seoul()
            today_date_seoul = now_seoul_tz.date()

            for student in all_students:
                if student.last_status_change and not student.last_leave_time:
                    last_change = student.last_status_change
                    if last_change.tzinfo is None:
                        last_change = last_change.replace(tzinfo=timezone.utc)
                    else:
                        last_change = last_change.astimezone(timezone.utc)

                    # 서울 시간으로 변환 후 날짜 비교
                    last_change_seoul = last_change.astimezone(SEOUL_TZ)
                    if last_change_seoul.date() == today_date_seoul:
                        self.joined_students_today.add(student.id)
            
            # 동기화 완료 후 is_restoring 해제
            self.is_restoring = False
            
            if self.monitor_service:
                await asyncio.sleep(0.5)
                await self.monitor_service.broadcast_dashboard_update_now()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            self.is_restoring = False
    
    def get_joined_students_today(self) -> set:
        return self.joined_students_today
    
    async def start(self):
        """Slack 리스너 시작 (동기화 포함)"""
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
    
    async def start_listener(self):
        """Socket Mode 리스너만 시작 (동기화 제외)"""
        try:
            if not self.handler:
                self.handler = AsyncSocketModeHandler(
                    self.app,
                    config.SLACK_APP_TOKEN
                )
            
            await self.handler.start_async()
        except Exception as e:
            raise
    
    async def stop(self):
        if self.handler:
            await self.handler.close_async()
