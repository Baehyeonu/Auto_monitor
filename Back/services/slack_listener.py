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
from utils.name_utils import extract_all_korean_names, extract_name_only

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
        self.logged_match_failures: set = set()  # 이미 로그 출력한 매칭 실패 이름들

        # 폴링 메커니즘 (Socket Mode 누락 메시지 보완)
        self.last_poll_timestamp = datetime.now().timestamp()
        self.polling_interval = 5  # 5초마다 폴링
        self.polling_task = None

        # 주기적 동기화 (10분마다 전체 상태 재동기화)
        self.periodic_sync_interval = 600  # 10분
        self.periodic_sync_task = None

        # 초기화 중 이벤트 큐
        self.pending_events: Queue = Queue()
        self.processing_pending = False
        
        self.role_keywords = {
            "조교", "주강사", "멘토", "매니저", "코치",
            "개발자", "학생", "수강생", "교육생",
            "강사", "관리자", "운영자", "팀장", "회장",
            "강의", "실습", "프로젝트", "팀"
        }
        self.ignore_keywords: List[str] = self._load_ignore_keywords()
        
        # 한글 패턴
        self.pattern_cam_on = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님(?:의|이)?\s*카메라(?:를|가)\s*(?:켰습니다|on\s*되었습니다)")
        self.pattern_cam_off = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님(?:의|이)?\s*카메라(?:를|가)\s*(?:껐습니다|off\s*되었습니다)")
        self.pattern_leave = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님이?\s*.*(퇴장|접속\s*종료|접속을\s*종료|나갔습니다)(?:했습니다)?")
        self.pattern_join = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님이?\s*.*(입장|접속했습니다|들어왔습니다)")

        # 영어 패턴 추가
        self.pattern_cam_on_en = re.compile(r"([^\s\[\]:]+?)\s*'?s?\s*camera\s*has\s*been\s*turned\s*on", re.IGNORECASE)
        self.pattern_cam_off_en = re.compile(r"([^\s\[\]:]+?)\s*'?s?\s*camera\s*has\s*been\s*turned\s*off", re.IGNORECASE)
        self.pattern_join_en = re.compile(r"([^\s\[\]:]+?)\s*(?:님이?)?\s*(?:has\s*)?(?:entered|joined|connected)", re.IGNORECASE)
        self.pattern_leave_en = re.compile(r"([^\s\[\]:]+?)\s*(?:님이?)?\s*(?:has\s*)?(?:left|exited|disconnected)", re.IGNORECASE)

        # 이벤트 핸들러 등록 (모든 메시지 타입 수신)
        self.app.message()(self._handle_all_messages)
    
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
                korean_names = extract_all_korean_names(student.zep_name, role_keywords=self.role_keywords)
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
    
    async def _handle_all_messages(self, message, say):
        """모든 메시지 핸들러 (일반 메시지 + 봇 메시지)"""
        try:
            channel = message.get("channel", "")
            # blocks에서 텍스트 추출 (attachments 포함)
            text = self._extract_text_from_blocks(message)
            message_ts_str = message.get("ts", "")
            message_ts = float(message_ts_str) if message_ts_str else 0
            subtype = message.get("subtype", "")

            # message_changed, message_deleted 등의 이벤트는 조용히 무시
            # (메시지 수정/삭제는 처리하지 않음)
            if subtype in ["message_changed", "message_deleted", "message_replied"]:
                return

            # 기존 채널: 카메라/입장/퇴장
            if channel == config.SLACK_CHANNEL_ID:
                asyncio.create_task(self._process_message_async(text, message_ts))
        except Exception as e:
            logger.error(f"[Slack 메시지 핸들러 오류] {e}", exc_info=True)
    
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
                return
            
            current_time = datetime.now().timestamp()
            if message_ts < self.start_time:
                if (current_time - message_ts) > 60:
                    return
            
            message_dt = datetime.fromtimestamp(message_ts, tz=timezone.utc) if message_ts > 0 else None

            # 카메라 ON (한글 + 영어)
            match_on = self.pattern_cam_on.search(text) or self.pattern_cam_on_en.search(text)
            if match_on:
                zep_name_raw = match_on.group(1)
                if self._should_ignore_name(zep_name_raw):
                    return
                zep_name = extract_name_only(zep_name_raw, role_keywords=self.role_keywords)
                await self._handle_camera_on(zep_name_raw, zep_name, message_dt, message_ts)
                return

            # 카메라 OFF (한글 + 영어)
            match_off = self.pattern_cam_off.search(text) or self.pattern_cam_off_en.search(text)
            if match_off:
                zep_name_raw = match_off.group(1)
                if self._should_ignore_name(zep_name_raw):
                    return
                zep_name = extract_name_only(zep_name_raw, role_keywords=self.role_keywords)
                await self._handle_camera_off(zep_name_raw, zep_name, message_dt, message_ts)
                return

            # 퇴장 (한글 + 영어)
            match_leave = self.pattern_leave.search(text) or self.pattern_leave_en.search(text)
            if match_leave:
                zep_name_raw = match_leave.group(1)
                if self._should_ignore_name(zep_name_raw):
                    return
                zep_name = extract_name_only(zep_name_raw, role_keywords=self.role_keywords)
                await self._handle_user_leave(zep_name_raw, zep_name, message_dt, message_ts)
                return

            # 입장 (한글 + 영어)
            match_join = self.pattern_join.search(text) or self.pattern_join_en.search(text)
            if match_join:
                zep_name_raw = match_join.group(1)
                if self._should_ignore_name(zep_name_raw):
                    return
                zep_name = extract_name_only(zep_name_raw, role_keywords=self.role_keywords)
                await self._handle_user_join(zep_name_raw, zep_name, message_dt, message_ts)
                return
        except Exception as e:
            logger.error(f"[메시지 처리 오류] 텍스트: '{text[:100]}', 오류: {e}", exc_info=True)
    
    async def _handle_camera_on(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0, add_to_joined_today: bool = True):
        try:
            student_id = None
            matched_name = zep_name

            for name in extract_all_korean_names(zep_name_raw, role_keywords=self.role_keywords):
                if name in self.student_cache:
                    student_id = self.student_cache[name]
                    student = await self.db_service.get_student_by_id(student_id)
                    if student:
                        matched_name = student.zep_name
                    break

            if not student_id:
                student = await self.db_service.get_student_by_zep_name(zep_name_raw)
                if not student:
                    for name in extract_all_korean_names(zep_name_raw, role_keywords=self.role_keywords):
                        student = await self.db_service.get_student_by_zep_name(name)
                        if student:
                            break

                if student:
                    student_id = student.id
                    matched_name = student.zep_name
                    self.student_cache[matched_name] = student_id
                    for name in extract_all_korean_names(zep_name_raw, role_keywords=self.role_keywords):
                        if name not in self.student_cache:
                            self.student_cache[name] = student_id

            if not student_id:
                # 중복 로그 방지: 같은 이름은 한 번만 로그 (* 제거 후 비교)
                normalized_name = zep_name_raw.strip('*').strip()
                if normalized_name not in self.logged_match_failures:
                    self.logged_match_failures.add(normalized_name)
                    logger.warning(f"[매칭 실패 - 카메라 ON] ZEP 이름: '{zep_name_raw}'")
                return

            if self._is_duplicate_event(student_id, "camera_on", message_ts):
                return

            if add_to_joined_today:
                self.joined_students_today.add(student_id)
            await self.db_service.clear_absent_status(student_id)
            # 오늘 이벤트가 아니면 last_status_change 업데이트 안함
            # message_timestamp가 None이면 현재 시간 사용 (실시간 이벤트 처리)
            if add_to_joined_today:
                timestamp_to_use = message_timestamp if message_timestamp else datetime.now(timezone.utc)
            else:
                timestamp_to_use = None
            success = await self.db_service.update_camera_status(
                matched_name,
                True,
                timestamp_to_use,
                is_restoring=self.is_restoring
            )

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
            
            for name in extract_all_korean_names(zep_name_raw, role_keywords=self.role_keywords):
                if name in self.student_cache:
                    student_id = self.student_cache[name]
                    student = await self.db_service.get_student_by_id(student_id)
                    if student:
                        matched_name = student.zep_name
                    break
            
            if not student_id:
                student = await self.db_service.get_student_by_zep_name(zep_name_raw)
                if not student:
                    for name in extract_all_korean_names(zep_name_raw, role_keywords=self.role_keywords):
                        student = await self.db_service.get_student_by_zep_name(name)
                        if student:
                            break
                
                if student:
                    student_id = student.id
                    matched_name = student.zep_name
                    self.student_cache[matched_name] = student_id
                    for name in extract_all_korean_names(zep_name_raw, role_keywords=self.role_keywords):
                        if name not in self.student_cache:
                            self.student_cache[name] = student_id

            if not student_id:
                # 중복 로그 방지: 같은 이름은 한 번만 로그 (* 제거 후 비교)
                normalized_name = zep_name_raw.strip('*').strip()
                if normalized_name not in self.logged_match_failures:
                    self.logged_match_failures.add(normalized_name)
                    logger.warning(f"[매칭 실패 - 카메라 OFF] ZEP 이름: '{zep_name_raw}'")
                return

            if self._is_duplicate_event(student_id, "camera_off", message_ts):
                return
            
            if add_to_joined_today:
                self.joined_students_today.add(student_id)
            # 오늘 이벤트가 아니면 last_status_change 업데이트 안함
            # message_timestamp가 None이면 현재 시간 사용 (실시간 이벤트 처리)
            if add_to_joined_today:
                timestamp_to_use = message_timestamp if message_timestamp else datetime.now(timezone.utc)
            else:
                timestamp_to_use = None
            success = await self.db_service.update_camera_status(
                matched_name,
                False,
                timestamp_to_use,
                is_restoring=self.is_restoring
            )

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

            extracted = extract_all_korean_names(zep_name_raw, role_keywords=self.role_keywords)

            for name in extracted:
                if name in self.student_cache:
                    student_id = self.student_cache[name]
                    student = await self.db_service.get_student_by_id(student_id)
                    if student:
                        matched_name = student.zep_name
                    break

            if not student_id:
                student = await self.db_service.get_student_by_zep_name(zep_name_raw)
                if not student:
                    extracted_names = extract_all_korean_names(zep_name_raw, role_keywords=self.role_keywords)
                    for name in extracted_names:
                        student = await self.db_service.get_student_by_zep_name(name)
                        if student:
                            break

                if student:
                    student_id = student.id
                    matched_name = student.zep_name
                    self.student_cache[matched_name] = student_id
                    for name in extract_all_korean_names(zep_name_raw, role_keywords=self.role_keywords):
                        if name not in self.student_cache:
                            self.student_cache[name] = student_id

            if not student_id:
                # 중복 로그 방지: 같은 이름은 한 번만 로그 (* 제거 후 비교)
                normalized_name = zep_name_raw.strip('*').strip()
                if normalized_name not in self.logged_match_failures:
                    self.logged_match_failures.add(normalized_name)
                    logger.warning(f"[매칭 실패 - 입장] ZEP 이름: '{zep_name_raw}'")
                return

            if self._is_duplicate_event(student_id, "user_join", message_ts):
                return
            
            if add_to_joined_today:
                self.joined_students_today.add(student_id)

            await self.db_service.clear_absent_status(student_id)
            # 오늘 이벤트가 아니면 last_status_change 업데이트 안함
            timestamp_to_use = message_timestamp if add_to_joined_today else None
            success = await self.db_service.update_camera_status(matched_name, False, timestamp_to_use, is_restoring=self.is_restoring)

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
    
    async def _handle_user_leave(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None, message_ts: float = 0, add_to_joined_today: bool = True):
        try:
            student_id = None
            matched_name = zep_name
            korean_names = extract_all_korean_names(zep_name_raw, role_keywords=self.role_keywords)
            
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
                # 중복 로그 방지: 같은 이름은 한 번만 로그 (* 제거 후 비교)
                normalized_name = zep_name_raw.strip('*').strip()
                if normalized_name not in self.logged_match_failures:
                    self.logged_match_failures.add(normalized_name)
                    logger.warning(f"[매칭 실패 - 퇴장] ZEP 이름: '{zep_name_raw}'")
                return

            if self._is_duplicate_event(student_id, "user_leave", message_ts):
                return

            # 오늘 이벤트만 퇴장 시간 기록
            if add_to_joined_today:
                await self.db_service.record_user_leave(student_id)
            # 오늘 이벤트가 아니면 last_status_change 업데이트 안함
            timestamp_to_use = message_timestamp if add_to_joined_today else None
            success = await self.db_service.update_camera_status(matched_name, False, timestamp_to_use, is_restoring=self.is_restoring)

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
            # 디버깅: 현재 config 값 출력

            self.is_restoring = True
            self.joined_students_today.clear()
            self.last_event_times.clear()
            self.logged_match_failures.clear()  # 매칭 실패 로그 기록 초기화

            await self._refresh_student_cache()

            # monitor_service의 reset_time 사용 (UTC 기준)
            now_utc = datetime.now(timezone.utc)
            now_local = datetime.now()

            if self.monitor_service and self.monitor_service.reset_time:
                # monitor_service의 reset_time 사용 (이미 UTC)
                reset_time_utc = self.monitor_service.reset_time
                today_reset_ts = reset_time_utc.timestamp()
                # lookback_hours만큼 이전부터 조회
                oldest_dt = reset_time_utc - timedelta(hours=lookback_hours)
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
                    oldest_dt = today_reset_utc - timedelta(hours=lookback_hours)
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
                    logger.warning(f"Slack 채널 조회 실패: {error}")
                    break

                batch = response.get("messages", [])
                messages.extend(batch)

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            if not messages:
                logger.info("[동기화] 메시지 없음 - 종료")
                return
            
            messages.sort(key=lambda msg: float(msg.get("ts", 0)))
            
            processed_count = 0
            camera_on_count = 0
            camera_off_count = 0
            join_count = 0
            leave_count = 0
            
            for message in messages:
                text = message.get("text", "")
                if not text:
                    text = self._extract_text_from_blocks(message)
                if not text:
                    continue
                message_ts = float(message.get("ts", 0))
                message_dt = datetime.fromtimestamp(message_ts, tz=timezone.utc) if message_ts > 0 else None

                # 카메라 ON (한글 + 영어)
                match_on = self.pattern_cam_on.search(text) or self.pattern_cam_on_en.search(text)
                if match_on:
                    zep_name_raw = match_on.group(1)
                    zep_name = extract_name_only(zep_name_raw, role_keywords=self.role_keywords)
                    add_to_joined = message_ts >= today_reset_ts
                    await self._handle_camera_on(zep_name_raw, zep_name, message_dt, message_ts, add_to_joined_today=add_to_joined)
                    camera_on_count += 1
                    processed_count += 1
                    continue

                # 카메라 OFF (한글 + 영어)
                match_off = self.pattern_cam_off.search(text) or self.pattern_cam_off_en.search(text)
                if match_off:
                    zep_name_raw = match_off.group(1)
                    zep_name = extract_name_only(zep_name_raw, role_keywords=self.role_keywords)
                    add_to_joined = message_ts >= today_reset_ts
                    await self._handle_camera_off(zep_name_raw, zep_name, message_dt, message_ts, add_to_joined_today=add_to_joined)
                    camera_off_count += 1
                    processed_count += 1
                    continue

                # 퇴장 (한글 + 영어)
                match_leave = self.pattern_leave.search(text) or self.pattern_leave_en.search(text)
                if match_leave:
                    zep_name_raw = match_leave.group(1)
                    zep_name = extract_name_only(zep_name_raw, role_keywords=self.role_keywords)
                    add_to_joined = message_ts >= today_reset_ts
                    await self._handle_user_leave(zep_name_raw, zep_name, message_dt, message_ts, add_to_joined_today=add_to_joined)
                    leave_count += 1
                    processed_count += 1
                    continue

                # 입장 (한글 + 영어)
                match_join = self.pattern_join.search(text) or self.pattern_join_en.search(text)
                if match_join:
                    zep_name_raw = match_join.group(1)
                    zep_name = extract_name_only(zep_name_raw, role_keywords=self.role_keywords)
                    if message_ts >= today_reset_ts:
                        await self._handle_user_join(zep_name_raw, zep_name, message_dt, message_ts)
                        join_count += 1
                    else:
                        await self._handle_user_join(zep_name_raw, zep_name, message_dt, message_ts, add_to_joined_today=False)
                    processed_count += 1
                    continue

            # 백엔드 재시작/동기화 시: 응답 관련 필드만 초기화 (쿨다운 타이머는 유지)
            await self.db_service.reset_alert_fields_partial()

            # joined_students_today 복원: DB의 last_status_change를 기준으로 오늘 접속한 학생 추가
            all_students = await self.db_service.get_all_students()

            # 서울 시간 기준 오늘 날짜
            from database.db_service import now_seoul, SEOUL_TZ
            now_seoul_tz = now_seoul()
            today_date_seoul = now_seoul_tz.date()

            for student in all_students:
                # 오늘 상태 변경이 있는 학생은 모두 joined_students_today에 추가
                # (퇴장한 학생도 오늘 입장했던 학생이므로 포함)
                if student.last_status_change:
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
            logger.error(f"[restore_state_from_history 오류] {e}", exc_info=True)
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

            # 상태 채널 접근 테스트
            if config.STATUS_PARSING_ENABLED and config.SLACK_STATUS_CHANNEL_ID:
                logger.info(f"[상태 채널 테스트] 채널 ID: {config.SLACK_STATUS_CHANNEL_ID}")
                try:
                    # 채널 정보 조회 테스트
                    channel_info = await self.app.client.conversations_info(
                        channel=config.SLACK_STATUS_CHANNEL_ID
                    )
                    if channel_info.get("ok"):
                        channel_name = channel_info.get("channel", {}).get("name", "알 수 없음")
                        is_member = channel_info.get("channel", {}).get("is_member", False)
                        logger.info(f"[상태 채널 접근 성공] 채널명: {channel_name}, Bot 멤버 여부: {is_member}")
                        if not is_member:
                            logger.warning(f"⚠️ Bot이 상태 채널({channel_name})의 멤버가 아닙니다. '/invite @봇이름'으로 초대하세요.")
                    else:
                        error = channel_info.get("error", "unknown")
                        logger.error(f"[상태 채널 접근 실패] {error}")
                except Exception as e:
                    logger.error(f"[상태 채널 테스트 실패] {e}")

            await self.restore_state_from_history(lookback_hours=24)

            # 폴링 태스크 시작 (백그라운드)
            self.polling_task = asyncio.create_task(self._poll_missing_messages())
            logger.info(f"[폴링 시작] {self.polling_interval}초 간격으로 누락 메시지 체크")

            # 주기 동기화 태스크 시작 (백그라운드)
            self.periodic_sync_task = asyncio.create_task(self._periodic_sync())
            logger.info(f"[주기 동기화 시작] {self.periodic_sync_interval // 60}분 간격으로 상태 재동기화")

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

            # 폴링 태스크 시작 (백그라운드)
            if not self.polling_task or self.polling_task.done():
                self.polling_task = asyncio.create_task(self._poll_missing_messages())
                print(f"[폴링 시작] {self.polling_interval}초 간격으로 누락 메시지 체크")
                logger.info(f"[폴링 시작] {self.polling_interval}초 간격으로 누락 메시지 체크")

            # 주기 동기화 태스크 시작 (백그라운드)
            if not self.periodic_sync_task or self.periodic_sync_task.done():
                self.periodic_sync_task = asyncio.create_task(self._periodic_sync())
                print(f"[주기 동기화 시작] {self.periodic_sync_interval // 60}분 간격으로 상태 재동기화")
                logger.info(f"[주기 동기화 시작] {self.periodic_sync_interval // 60}분 간격으로 상태 재동기화")

            await self.handler.start_async()
        except Exception as e:
            raise
    
    async def _poll_missing_messages(self):
        """주기적으로 Slack API를 폴링해서 Socket Mode에서 누락된 메시지 처리"""
        while True:
            try:
                await asyncio.sleep(self.polling_interval)

                # 마지막 폴링 이후의 메시지만 조회
                now_ts = datetime.now().timestamp()

                # 일반 채널 폴링
                response = await self.app.client.conversations_history(
                    channel=config.SLACK_CHANNEL_ID,
                    oldest=str(self.last_poll_timestamp),
                    limit=100
                )

                if not response.get("ok"):
                    logger.error(f"[폴링 실패] Slack API 오류: {response.get('error')}")
                else:
                    messages = response.get("messages", [])
                    messages.reverse()

                    processed_count = 0
                    for msg in messages:
                        # bot_message만 처리
                        if msg.get("subtype") != "bot_message":
                            continue

                        text = msg.get("text", "")
                        if not text:
                            text = self._extract_text_from_blocks(msg)
                        message_ts = float(msg.get("ts", 0))

                        # 이미 처리한 메시지는 스킵 (타임스탬프 기준)
                        if message_ts <= self.last_poll_timestamp:
                            continue

                        # 메시지 처리
                        await self._process_message_async(text, message_ts)
                        processed_count += 1

                    if processed_count > 0:
                        logger.info(f"[폴링 완료] {processed_count}개 누락 메시지 처리")

                # 타임스탬프 업데이트
                self.last_poll_timestamp = now_ts

            except Exception as e:
                logger.error(f"[폴링 오류] {e}", exc_info=True)
                await asyncio.sleep(5)  # 오류 발생 시 5초 대기

    async def _periodic_sync(self):
        """10분마다 전체 상태 동기화 (빠른 연속 이벤트 누락 방지)"""
        while True:
            try:
                await asyncio.sleep(self.periodic_sync_interval)

                logger.info("[주기 동기화] 시작 - 최근 1시간 메시지 재동기화")

                # 최근 1시간만 동기화 (빠른 이벤트 처리 위주)
                await self.restore_state_from_history(lookback_hours=1)

                logger.info("[주기 동기화] 완료")

            except Exception as e:
                logger.error(f"[주기 동기화 오류] {e}", exc_info=True)
                await asyncio.sleep(60)  # 오류 발생 시 1분 후 재시도

    def _extract_text_from_blocks(self, message: dict) -> str:
        """Slack blocks에서 텍스트 추출 (attachments 포함)"""
        text_parts = []

        # 1. message.blocks 처리 (일반 메시지)
        blocks = message.get("blocks", [])
        if blocks:
            for block in blocks:
                block_type = block.get("type")

                # section 블록
                if block_type == "section":
                    if "text" in block:
                        text_parts.append(block["text"].get("text", ""))
                    if "fields" in block:
                        for field in block["fields"]:
                            text_parts.append(field.get("text", ""))

                # context 블록
                elif block_type == "context":
                    elements = block.get("elements", [])
                    for elem in elements:
                        if elem.get("type") == "mrkdwn":
                            text_parts.append(elem.get("text", ""))

                # rich_text 블록 (사용자가 직접 입력한 메시지)
                elif block_type == "rich_text":
                    elements = block.get("elements", [])
                    for element in elements:
                        if element.get("type") == "rich_text_section":
                            inner_elements = element.get("elements", [])
                            for inner in inner_elements:
                                if inner.get("type") == "text":
                                    text_parts.append(inner.get("text", ""))
                                elif inner.get("type") == "emoji":
                                    text_parts.append(f":{inner.get('name', '')}:")
                                elif inner.get("type") == "user":
                                    text_parts.append(f"<@{inner.get('user_id', '')}>")
                        elif element.get("type") == "rich_text_list":
                            # 리스트 처리 (필요시)
                            pass

        # 2. message.attachments[].blocks 처리 (봇 메시지)
        attachments = message.get("attachments", [])
        for attachment in attachments:
            att_blocks = attachment.get("blocks", [])
            for block in att_blocks:
                block_type = block.get("type")

                # section 블록
                if block_type == "section":
                    if "text" in block:
                        text_parts.append(block["text"].get("text", ""))
                    if "fields" in block:
                        for field in block["fields"]:
                            text_parts.append(field.get("text", ""))

                # context 블록
                elif block_type == "context":
                    elements = block.get("elements", [])
                    for elem in elements:
                        if elem.get("type") == "mrkdwn":
                            text_parts.append(elem.get("text", ""))

        # 3. 추출된 텍스트가 있으면 반환
        if text_parts:
            return "\n".join(text_parts)

        # 4. blocks가 없으면 일반 text 사용
        return message.get("text", "")

    async def stop(self):
        # 폴링 태스크 종료
        if self.polling_task and not self.polling_task.done():
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass

        # 주기 동기화 태스크 종료
        if self.periodic_sync_task and not self.periodic_sync_task.done():
            self.periodic_sync_task.cancel()
            try:
                await self.periodic_sync_task
            except asyncio.CancelledError:
                pass

        if self.handler:
            await self.handler.close_async()
