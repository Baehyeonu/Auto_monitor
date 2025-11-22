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
    """Slack 메시지 리스너 클래스"""
    
    def __init__(self, monitor_service=None):
        """
        Slack App 초기화
        
        Args:
            monitor_service: MonitorService 인스턴스 (초기화 진행 중 확인용)
        """
        self.app = AsyncApp(token=config.SLACK_BOT_TOKEN)
        self.handler = None
        self.db_service = DBService()
        self.monitor_service = monitor_service  # MonitorService 참조
        
        # 프로그램 시작 시간 기록 (과거 메시지 무시용)
        self.start_time = datetime.now().timestamp()
        
        # 상태 복원 플래그 (복원 중에는 알림 차단)
        self.is_restoring = False
        
        # 오늘 입장한 학생 ID 추적 (미접속 학생 구분용)
        self.joined_students_today = set()
        
        # 정규식 패턴 (다양한 메시지 형태 지원)
        # 형식: "[오후 2:48] [14:48] :no_entry_sign: *현우_조교* 님의 카메라가 off 되었습니다"
        # "님" 앞의 이름 추출 (볼드 마크 * 제거)
        self.pattern_cam_on = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님(?:의|이)?\s*카메라(?:를|가)\s*(?:켰습니다|on\s*되었습니다)")
        self.pattern_cam_off = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님(?:의|이)?\s*카메라(?:를|가)\s*(?:껐습니다|off\s*되었습니다)")
        self.pattern_leave = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님이?\s*.*(퇴장|접속\s*종료|접속을\s*종료|나갔습니다)(?:했습니다)?")
        self.pattern_join = re.compile(r"\*?([^\s\[\]:]+?)\*?\s*님이?\s*.*(입장|접속했습니다|들어왔습니다)")
        
        # 이벤트 핸들러 등록
        self._setup_handlers()
    
    def _extract_name_only(self, zep_name: str) -> str:
        """
        ZEP 이름에서 실제 이름만 추출 (다양한 구분자 지원)
        - "구마적/IH02" → "구마적"
        - "IH02/구마적" → "구마적"
        - "구마적-IH02" → "구마적"
        - "IH02_구마적" → "구마적"
        - "주강사_유승수" → "유승수" (마지막 한글 부분)
        - "구마적" → "구마적"
        
        Args:
            zep_name: Slack에서 추출한 전체 이름
            
        Returns:
            한글이 포함된 이름 부분만 반환 (역할명 제외하고 실제 이름 우선)
        """
        # 다양한 구분자로 분리: /, _, -, 공백 등
        # 정규식으로 여러 구분자를 한 번에 처리
        parts = re.split(r'[/_\-|\s]+', zep_name.strip())
        parts = [part.strip() for part in parts if part.strip()]
        
        # 한글이 포함된 부분들 모두 수집
        korean_parts = []
        for part in parts:
            # 한글 유니코드 범위: 가-힣
            if any('\uAC00' <= char <= '\uD7A3' for char in part):
                korean_parts.append(part)
        
        # 한글 부분이 여러 개면 마지막 것 반환 (역할명_이름 형식 대응)
        # 예: "주강사_유승수" → ["주강사", "유승수"] → "유승수"
        if len(korean_parts) > 1:
            return korean_parts[-1]
        elif len(korean_parts) == 1:
            return korean_parts[0]
        
        # 한글이 없으면 첫 번째 부분 반환 (기본값)
        if parts:
            return parts[0]
        
        # 빈 문자열이면 그대로 반환
        return zep_name.strip()
    
    def _extract_all_korean_names(self, zep_name: str) -> list:
        """
        ZEP 이름에서 한글 부분 모두 추출 (DB 매칭용)
        
        Args:
            zep_name: Slack에서 추출한 전체 이름
            
        Returns:
            한글 부분 리스트 (역순으로 반환 - 실제 이름이 뒤에 있을 가능성 높음)
        """
        parts = re.split(r'[/_\-|\s]+', zep_name.strip())
        parts = [part.strip() for part in parts if part.strip()]
        
        korean_parts = []
        for part in parts:
            if any('\uAC00' <= char <= '\uD7A3' for char in part):
                korean_parts.append(part)
        
        # 역순으로 반환 (마지막 한글 부분이 실제 이름일 가능성 높음)
        return list(reversed(korean_parts)) if korean_parts else [zep_name.strip()]
    
    def _setup_handlers(self):
        """Slack 이벤트 핸들러 설정"""
        
        @self.app.event("message")
        async def handle_message(event, say):
            """메시지 이벤트 처리"""
            # 초기화 진행 중이면 로그 처리 스킵
            if self.monitor_service and self.monitor_service.is_resetting:
                return  # 초기화 완료까지 대기
            
            # 메시지 타임스탬프 확인 (과거 메시지 무시)
            message_ts = float(event.get("ts", 0))
            if message_ts < self.start_time:
                # 프로그램 시작 전 메시지는 무시
                return
            
            text = event.get("text", "")
            
            # 카메라 ON 메시지
            match_on = self.pattern_cam_on.search(text)
            if match_on:
                zep_name_raw = match_on.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_camera_on(zep_name_raw, zep_name)
                return
            
            # 카메라 OFF 메시지
            match_off = self.pattern_cam_off.search(text)
            if match_off:
                zep_name_raw = match_off.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_camera_off(zep_name_raw, zep_name)
                return
            
            # 퇴장/접속 종료 메시지 (먼저 체크!)
            match_leave = self.pattern_leave.search(text)
            if match_leave:
                zep_name_raw = match_leave.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_user_leave(zep_name_raw, zep_name)
                return
            
            # 입장/접속 메시지 (퇴장 이후 체크)
            match_join = self.pattern_join.search(text)
            if match_join:
                zep_name_raw = match_join.group(1)
                zep_name = self._extract_name_only(zep_name_raw)
                await self._handle_user_join(zep_name_raw, zep_name)
                return
    
    async def _handle_camera_on(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None):
        """
        카메라 ON 이벤트 처리
        
        Args:
            zep_name_raw: ZEP 원본 이름 (로그용, 예: "현우_조교", "주강사_유승수")
            zep_name: 추출된 이름 (DB 조회용, 예: "현우", "유승수")
            message_timestamp: 메시지 타임스탬프 (히스토리 복원 시 사용, None이면 현재 시간)
        """
        current_time = datetime.now().strftime("%H:%M")
        if not self.is_restoring:
            print(f"📷 [{current_time}] 카메라 ON: {zep_name_raw}")
        
        # DB에서 학생 확인 (모든 한글 부분 시도)
        student = None
        matched_name = zep_name
        for name in self._extract_all_korean_names(zep_name_raw):
            student = await self.db_service.get_student_by_zep_name(name)
            if student:
                matched_name = name
                break
        
        if student:
            # 외출/조퇴 상태면 복귀로 간주하고 상태 초기화
            if student.is_absent:
                await self.db_service.clear_absent_status(student.id)
                if not self.is_restoring:
                    absent_type_text = "외출" if student.absent_type == "leave" else "조퇴"
                    print(f"   🏠 {zep_name_raw} 복귀 확인 ({absent_type_text} → 복귀)")
            
            # 상태 업데이트 (알림 기록 초기화, 히스토리 복원 시 메시지 타임스탬프 사용)
            success = await self.db_service.update_camera_status(matched_name, True, message_timestamp)
            if success and not self.is_restoring:
                print(f"   ✅ {zep_name_raw} 카메라: ON (알림 초기화)")
                
                # WebSocket 브로드캐스트
                await manager.broadcast_student_status_changed(
                    student_id=student.id,
                    zep_name=student.zep_name,
                    event_type='camera_on',
                    is_cam_on=True,
                    elapsed_minutes=0
                )
                # 대시보드 즉시 업데이트
                if self.monitor_service:
                    print(f"🔄 대시보드 즉시 업데이트 요청: {zep_name_raw} 카메라 ON")
                    await self.monitor_service.broadcast_dashboard_update_now()
                else:
                    print(f"⚠️ monitor_service가 None입니다. 대시보드 업데이트 불가")
            elif not success and not self.is_restoring:
                print(f"   ❌ {zep_name_raw} 상태 업데이트 실패")
        elif not self.is_restoring:
            print(f"   ⚠️ {zep_name_raw}은(는) 등록되지 않은 학생입니다.")
    
    async def _handle_camera_off(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None):
        """
        카메라 OFF 이벤트 처리
        
        Args:
            zep_name_raw: ZEP 원본 이름 (로그용, 예: "현우_조교", "주강사_유승수")
            zep_name: 추출된 이름 (DB 조회용, 예: "현우", "유승수")
            message_timestamp: 메시지 타임스탬프 (히스토리 복원 시 사용, None이면 현재 시간)
        """
        current_time = datetime.now().strftime("%H:%M")
        if not self.is_restoring:
            print(f"📷 [{current_time}] 카메라 OFF: {zep_name_raw}")
        
        # DB에서 학생 확인 (모든 한글 부분 시도)
        student = None
        matched_name = zep_name
        for name in self._extract_all_korean_names(zep_name_raw):
            student = await self.db_service.get_student_by_zep_name(name)
            if student:
                matched_name = name
                break
        
        if student:
            # 상태 업데이트 (히스토리 복원 시 메시지 타임스탬프 사용)
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)
            if success and not self.is_restoring:
                print(f"   ⚠️ {zep_name_raw} 카메라: OFF")
                
                # WebSocket 브로드캐스트
                await manager.broadcast_student_status_changed(
                    student_id=student.id,
                    zep_name=student.zep_name,
                    event_type='camera_off',
                    is_cam_on=False,
                    elapsed_minutes=0
                )
                # 대시보드 즉시 업데이트
                if self.monitor_service:
                    print(f"🔄 대시보드 즉시 업데이트 요청: {zep_name_raw} 카메라 ON")
                    await self.monitor_service.broadcast_dashboard_update_now()
                else:
                    print(f"⚠️ monitor_service가 None입니다. 대시보드 업데이트 불가")
            elif not success and not self.is_restoring:
                print(f"   ❌ {zep_name_raw} 상태 업데이트 실패")
        elif not self.is_restoring:
            print(f"   ⚠️ {zep_name_raw}은(는) 등록되지 않은 학생입니다.")
    
    async def _handle_user_join(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None):
        """
        유저 입장/접속 이벤트 처리
        
        Args:
            zep_name_raw: ZEP 원본 이름 (로그용, 예: "현우_조교", "주강사_유승수")
            zep_name: 추출된 이름 (DB 조회용, 예: "현우", "유승수")
            message_timestamp: 메시지 타임스탬프 (히스토리 복원 시 사용, None이면 현재 시간)
        """
        current_time = datetime.now().strftime("%H:%M")
        if not self.is_restoring:
            print(f"🟢 [{current_time}] 유저 입장: {zep_name_raw}")
        
        # DB에서 학생 확인 (모든 한글 부분 시도)
        student = None
        matched_name = zep_name
        for name in self._extract_all_korean_names(zep_name_raw):
            student = await self.db_service.get_student_by_zep_name(name)
            if student:
                matched_name = name
                break
        
        if student:
            # 오늘 입장한 학생으로 기록
            self.joined_students_today.add(student.id)
            
            # 외출/조퇴 상태면 복귀로 간주하고 상태 초기화
            if student.is_absent and not self.is_restoring:
                absent_type_text = "외출" if student.absent_type == "leave" else "조퇴"
                print(f"   🏠 {zep_name_raw} 복귀 확인 ({absent_type_text} → 복귀)")
            
            # 입장 시 외출/조퇴 상태 초기화
            await self.db_service.clear_absent_status(student.id)
            # 입장 시 카메라 상태를 OFF로 설정 (ZEP 기본값, 히스토리 복원 시 메시지 타임스탬프 사용)
            await self.db_service.update_camera_status(matched_name, False, message_timestamp)
            if not self.is_restoring:
                print(f"   ✅ {zep_name_raw} 입장 확인됨 (카메라: OFF)")
                
                # WebSocket 브로드캐스트
                await manager.broadcast_student_status_changed(
                    student_id=student.id,
                    zep_name=student.zep_name,
                    event_type='user_join',
                    is_cam_on=False,
                    elapsed_minutes=0
                )
                # 대시보드 즉시 업데이트
                if self.monitor_service:
                    print(f"🔄 대시보드 즉시 업데이트 요청: {zep_name_raw} 카메라 ON")
                    await self.monitor_service.broadcast_dashboard_update_now()
                else:
                    print(f"⚠️ monitor_service가 None입니다. 대시보드 업데이트 불가")
        elif not self.is_restoring:
            print(f"   ⚠️ {zep_name_raw}은(는) 등록되지 않은 학생입니다.")
    
    async def _handle_user_leave(self, zep_name_raw: str, zep_name: str, message_timestamp: Optional[datetime] = None):
        """
        유저 퇴장/접속 종료 이벤트 처리
        
        Args:
            zep_name_raw: ZEP 원본 이름 (로그용, 예: "현우_조교", "주강사_유승수")
            zep_name: 추출된 이름 (DB 조회용, 예: "현우", "유승수")
            message_timestamp: 메시지 타임스탬프 (히스토리 복원 시 사용, None이면 현재 시간)
        """
        current_time = datetime.now().strftime("%H:%M")
        if not self.is_restoring:
            print(f"🔴 [{current_time}] 유저 퇴장: {zep_name_raw}")
        
        # DB에서 학생 확인 (모든 한글 부분 시도)
        student = None
        matched_name = zep_name
        korean_names = self._extract_all_korean_names(zep_name_raw)
        
        for name in korean_names:
            student = await self.db_service.get_student_by_zep_name(name)
            if student:
                matched_name = name
                break
        
        if student:
            # 퇴장 시 접속 종료 시간 기록
            await self.db_service.record_user_leave(student.id)
            # 퇴장 시 카메라 상태를 OFF로 설정 (20분 후 카메라 알림, 30분 후 접속 종료 알림, 히스토리 복원 시 메시지 타임스탬프 사용)
            success = await self.db_service.update_camera_status(matched_name, False, message_timestamp)
            if success and not self.is_restoring:
                print(f"   ✅ {zep_name_raw} 퇴장 확인됨 (접속 종료 기록)")
                
                # WebSocket 브로드캐스트
                await manager.broadcast_student_status_changed(
                    student_id=student.id,
                    zep_name=student.zep_name,
                    event_type='user_leave',
                    is_cam_on=False,
                    elapsed_minutes=0
                )
                # 대시보드 즉시 업데이트
                if self.monitor_service:
                    print(f"🔄 대시보드 즉시 업데이트 요청: {zep_name_raw} 카메라 ON")
                    await self.monitor_service.broadcast_dashboard_update_now()
                else:
                    print(f"⚠️ monitor_service가 None입니다. 대시보드 업데이트 불가")
            elif not self.is_restoring:
                print(f"   ✅ {zep_name_raw} 퇴장 확인됨 (접속 종료 기록)")
        else:
            if not self.is_restoring:
                print(f"   ⚠️ {zep_name_raw}은(는) 등록되지 않은 학생입니다. (시도한 이름: {korean_names})")
    
    async def restore_state_from_history(self, lookback_hours: int = 24):
        """
        Slack 메시지 히스토리를 조회해서 과거 상태 복원
        일일 초기화 시간 이후 메시지만 조회 (오늘 접속 안 한 학생 제외)
        
        Args:
            lookback_hours: 조회할 과거 시간 (기본 24시간, 초기화 시간이 없을 때만 사용)
        """
        try:
            self.is_restoring = True
            
            # 오늘 입장 기록 초기화
            self.joined_students_today.clear()
            
            # 히스토리 복원 전에 모든 학생의 상태 초기화
            # (오늘 접속하지 않은 학생은 모니터링 대상에서 제외)
            print("   🔄 카메라 및 접속 상태 초기화 중...")
            await self.db_service.reset_all_camera_status()
            
            # 조회 시작 시간 계산
            now = datetime.now()
            
            # 1. DAILY_RESET_TIME이 설정되어 있으면 오늘의 초기화 시간 이후부터
            if config.DAILY_RESET_TIME:
                from datetime import time as time_type
                try:
                    reset_time = datetime.strptime(config.DAILY_RESET_TIME, "%H:%M").time()
                    today_reset = datetime.combine(now.date(), reset_time)
                    
                    # 현재 시간이 초기화 시간 이전이면 어제의 초기화 시간부터
                    if now < today_reset:
                        oldest_dt = today_reset - timedelta(days=1)
                    else:
                        oldest_dt = today_reset
                    
                    print(f"🔄 {oldest_dt.strftime('%Y-%m-%d %H:%M')} 이후 메시지 히스토리 복원 중...")
                except ValueError:
                    # 초기화 시간 파싱 실패 시 오늘 00:00부터
                    oldest_dt = datetime.combine(now.date(), time_type(0, 0))
                    print(f"🔄 오늘 00:00 이후 메시지 히스토리 복원 중...")
            else:
                # 2. 초기화 시간이 없으면 오늘 00:00부터 (어제 데이터 제외)
                oldest_dt = datetime.combine(now.date(), datetime.min.time())
                print(f"🔄 오늘 00:00 이후 메시지 히스토리 복원 중...")
            
            oldest_ts = oldest_dt.timestamp()
            
            # Slack API로 메시지 히스토리 조회 (pagination 처리)
            messages = []
            cursor = None
            
            while True:
                response = await self.app.client.conversations_history(
                    channel=config.SLACK_CHANNEL_ID,
                    oldest=str(oldest_ts),
                    limit=1000,  # 최대 1000개 메시지
                    cursor=cursor
                )
                
                batch = response.get("messages", [])
                messages.extend(batch)
                
                # 다음 페이지가 있는지 확인
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
            
            print(f"   📥 총 {len(messages)}개 메시지 조회 완료")
            
            if not messages:
                print("   ℹ️ 조회된 메시지가 없습니다.")
                return
            
            # 메시지를 시간순으로 정렬 (오래된 것부터)
            messages.sort(key=lambda msg: float(msg.get("ts", 0)))
            
            processed_count = 0
            cam_on_count = 0
            cam_off_count = 0
            join_count = 0
            leave_count = 0
            
            # 각 메시지를 순서대로 처리 (실시간 처리와 동일한 순서)
            for message in messages:
                text = message.get("text", "")
                # Slack 메시지 타임스탬프를 datetime으로 변환 (Unix timestamp 초 단위)
                message_ts = float(message.get("ts", 0))
                message_dt = datetime.fromtimestamp(message_ts, tz=timezone.utc) if message_ts > 0 else None
                
                # 카메라 ON 메시지
                match_on = self.pattern_cam_on.search(text)
                if match_on:
                    zep_name_raw = match_on.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    await self._handle_camera_on(zep_name_raw, zep_name, message_dt)
                    cam_on_count += 1
                    processed_count += 1
                    continue
                
                # 카메라 OFF 메시지
                match_off = self.pattern_cam_off.search(text)
                if match_off:
                    zep_name_raw = match_off.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    await self._handle_camera_off(zep_name_raw, zep_name, message_dt)
                    cam_off_count += 1
                    processed_count += 1
                    continue
                
                # 퇴장/접속 종료 메시지 (카메라보다 우선 - 실시간 처리와 동일)
                match_leave = self.pattern_leave.search(text)
                if match_leave:
                    zep_name_raw = match_leave.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    await self._handle_user_leave(zep_name_raw, zep_name, message_dt)
                    leave_count += 1
                    processed_count += 1
                    continue
                
                # 입장/접속 메시지 (퇴장 이후 체크)
                match_join = self.pattern_join.search(text)
                if match_join:
                    zep_name_raw = match_join.group(1)
                    zep_name = self._extract_name_only(zep_name_raw)
                    await self._handle_user_join(zep_name_raw, zep_name, message_dt)
                    join_count += 1
                    processed_count += 1
                    continue
            
            print(f"   ✅ 복원 완료: {processed_count}개 이벤트 처리")
            print(f"      입장: {join_count}, 퇴장: {leave_count}")
            print(f"      카메라 ON: {cam_on_count}, OFF: {cam_off_count}")
            
            # 알림 필드 전체 초기화 (상태는 유지, 알림 타이머만 리셋)
            print(f"   🔄 알림 타이머 초기화 중...")
            await self.db_service.reset_all_alert_fields()
            print(f"   ✅ 알림 타이머 초기화 완료 (재시작 시점부터 새로 카운트)")
            
        except Exception as e:
            print(f"   ❌ 히스토리 복원 실패: {e}")
        finally:
            self.is_restoring = False
    
    def get_joined_students_today(self) -> set:
        """
        오늘 입장한 학생 ID 목록 반환
        
        Returns:
            오늘 입장한 학생 ID set
        """
        return self.joined_students_today
    
    async def start(self):
        """Slack Socket Mode 시작"""
        print("🔌 Slack Socket Mode 연결 중...")
        start_time_str = datetime.fromtimestamp(self.start_time).strftime("%H:%M")
        print(f"   ⏰ 프로그램 시작 시간: {start_time_str}")
        
        try:
            # Socket Mode 연결
            self.handler = AsyncSocketModeHandler(
                self.app,
                config.SLACK_APP_TOKEN
            )
            
            # 히스토리 복원 (재시작 시 과거 상태 복구)
            await self.restore_state_from_history(lookback_hours=24)
            
            # 실시간 모니터링 시작
            print("🎯 실시간 모니터링 시작...")
            await self.handler.start_async()
        except Exception as e:
            print(f"❌ Slack 연결 실패: {e}")
            raise
    
    async def stop(self):
        """Slack Socket Mode 종료"""
        if self.handler:
            await self.handler.close_async()
            print("🔌 Slack 연결 종료")

