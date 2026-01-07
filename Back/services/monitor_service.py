"""
모니터링 서비스
주기적으로 학생들의 카메라 상태를 체크하고 알림을 전송합니다.
"""
import asyncio
import logging
from datetime import datetime, time, timezone, date
from typing import Optional
from zoneinfo import ZoneInfo

from config import config
from database import DBService
from database.db_service import now_seoul, SEOUL_TZ
from utils.holiday_checker import HolidayChecker
from api.websocket_manager import manager
from utils.dashboard_utils import build_overview

logger = logging.getLogger(__name__)


class MonitorService:
    """모니터링 서비스 클래스"""
    
    def __init__(self, discord_bot):
        """
        모니터링 서비스 초기화
        
        Args:
            discord_bot: DiscordBot 인스턴스
        """
        self.discord_bot = discord_bot
        self.db_service = DBService()
        self.slack_listener = None
        self.is_running = False
        self.check_interval = config.CHECK_INTERVAL
        self.camera_off_threshold = config.CAMERA_OFF_THRESHOLD
        self.alert_cooldown = config.ALERT_COOLDOWN
        self.leave_alert_threshold = config.LEAVE_ALERT_THRESHOLD
        self.leave_admin_alert_cooldown = config.LEAVE_ADMIN_ALERT_COOLDOWN
        self.absent_alert_cooldown = config.ABSENT_ALERT_COOLDOWN
        self.return_reminder_time = config.RETURN_REMINDER_TIME
        self.start_time = None
        self.warmup_minutes = 1
        self.last_lunch_check = None
        self.last_class_check = None  # 수업 시작/종료 감지용
        self.daily_reset_time = self._parse_daily_reset_time(config.DAILY_RESET_TIME)
        self.last_daily_reset_date: Optional[str] = None
        self.reset_time: Optional[datetime] = None
        self.is_resetting = False
        self.is_dm_paused = False
        self.is_monitoring_paused = False
        self.holiday_checker = HolidayChecker()
    
    def set_slack_listener(self, slack_listener):
        """SlackListener 참조 설정 (순환 참조 방지)"""
        self.slack_listener = slack_listener
    
    async def start(self):
        """모니터링 시작"""
        self.is_running = True
        self.start_time = datetime.now(timezone.utc)
        
        await self._check_startup_reset()
        
        await self._start_monitoring_loop()
    
    async def start_without_reset(self):
        """모니터링 시작 (초기화 제외) - 이미 초기화가 완료된 경우 사용"""
        self.is_running = True
        self.start_time = datetime.now(timezone.utc)
        
        await self._start_monitoring_loop()
    
    async def _start_monitoring_loop(self):
        """모니터링 루프 시작 (공통 로직)"""
        print(f"👀 모니터링 서비스 시작 (체크 간격: {self.check_interval}초)")
        print(f"   • 카메라 OFF 임계값: {self.camera_off_threshold}분")
        print(f"   • 알림 쿨다운: {self.alert_cooldown}분")
        print(f"   • 접속 종료 알림 임계값: {self.leave_alert_threshold}분")
        print(f"   • 접속 종료 알림 쿨다운: {self.leave_admin_alert_cooldown}분")
        print(f"   • 외출/조퇴 알림 쿨다운: {self.absent_alert_cooldown}분")
        print(f"   • 복귀 요청 재알림 시간: {self.return_reminder_time}분")
        print(f"   • 워밍업 시간: {self.warmup_minutes}분 (시작 후 알림 안 보냄)")
        print(f"   • 수업 시간: {config.CLASS_START_TIME} ~ {config.CLASS_END_TIME}")
        print(f"   • 점심 시간: {config.LUNCH_START_TIME} ~ {config.LUNCH_END_TIME}")
        if self.daily_reset_time:
            print(f"   • 일일 초기화 시간: 매일 {self.daily_reset_time.strftime('%H:%M')}")
        else:
            print("   • 일일 초기화: 비활성화")
        
        asyncio.create_task(self._broadcast_dashboard_periodically())
        
        while self.is_running:
            try:
                await self._check_students()
            except Exception as e:
                print(f"❌ [모니터링] 체크 중 오류 발생: {e}")
                import traceback
                traceback.print_exc()
            finally:
                await asyncio.sleep(self.check_interval)
        
        print("🛑 [모니터링] 루프 종료")
    
    async def stop(self):
        """모니터링 중지"""
        self.is_running = False
        print("🛑 모니터링 서비스 중지")
    
    def pause_dm(self):
        """DM 발송 일시정지"""
        self.is_dm_paused = True
        print("🔕 DM 발송이 일시정지되었습니다.")
    
    def resume_dm(self):
        """DM 발송 재개"""
        self.is_dm_paused = False
        print("🔔 DM 발송이 재개되었습니다.")
    
    def pause_monitoring(self):
        """모니터링 일시정지 (수동 제어)"""
        self.is_monitoring_paused = True
        print("⏸️ 모니터링이 일시정지되었습니다.")
    
    def resume_monitoring(self):
        """모니터링 재개 (수동 제어)"""
        self.is_monitoring_paused = False
        print("▶️ 모니터링이 재개되었습니다.")

    def update_settings(self, **kwargs):
        """
        설정 실시간 업데이트

        Args:
            **kwargs: 업데이트할 설정 (camera_off_threshold, alert_cooldown, check_interval 등)
        """
        if 'camera_off_threshold' in kwargs:
            self.camera_off_threshold = kwargs['camera_off_threshold']
            print(f"⚙️ 카메라 OFF 임계값 변경: {self.camera_off_threshold}분")

        if 'alert_cooldown' in kwargs:
            self.alert_cooldown = kwargs['alert_cooldown']
            print(f"⚙️ 알림 쿨다운 변경: {self.alert_cooldown}분")

        if 'check_interval' in kwargs:
            self.check_interval = kwargs['check_interval']
            print(f"⚙️ 체크 간격 변경: {self.check_interval}초")

        if 'leave_alert_threshold' in kwargs:
            self.leave_alert_threshold = kwargs['leave_alert_threshold']
            print(f"⚙️ 접속 종료 알림 임계값 변경: {self.leave_alert_threshold}분")

        if 'daily_reset_time' in kwargs:
            self.daily_reset_time = self._parse_daily_reset_time(kwargs['daily_reset_time'])
            print(f"⚙️ 일일 초기화 시간 변경: {kwargs['daily_reset_time']}")

    def is_monitoring_active(self) -> bool:
        """
        모니터링이 활성화되어 있는지 확인
        
        Returns:
            활성화되어 있으면 True
        """
        if self.is_monitoring_paused:
            return False
        
        today = date.today()
        if self.holiday_checker.is_weekend_or_holiday(today):
            return False
        
        return True
    
    def _is_class_time(self) -> bool:
        """
        현재 시간이 수업 시간인지 확인

        Returns:
            bool: 수업 시간이면 True, 아니면 False
        """
        now = now_seoul()  # 서울 시간 사용
        current_time = now.time()

        try:
            class_start = datetime.strptime(config.CLASS_START_TIME, "%H:%M").time()
            class_end = datetime.strptime(config.CLASS_END_TIME, "%H:%M").time()
            lunch_start = datetime.strptime(config.LUNCH_START_TIME, "%H:%M").time()
            lunch_end = datetime.strptime(config.LUNCH_END_TIME, "%H:%M").time()
        except ValueError:
            return False

        if current_time < class_start:
            return False

        if current_time > class_end:
            return False

        # 점심시간: 시작 포함, 종료 미포함으로 통일
        if lunch_start <= current_time < lunch_end:
            return False

        return True
    
    async def _check_schedule_events(self, now: datetime):
        """수업/점심 시간 이벤트 체크 (모니터링 활성화 여부와 무관하게 실행)"""
        current_time = now.strftime("%H:%M")
        current_time_obj = now.time()
        
        # 수업 시작/종료 감지
        try:
            class_start = datetime.strptime(config.CLASS_START_TIME, "%H:%M").time()
            class_end = datetime.strptime(config.CLASS_END_TIME, "%H:%M").time()
            
            # 수업 시작 감지
            if current_time_obj >= class_start and self.last_class_check != "in_class":
                if current_time_obj < class_end:
                    await manager.broadcast_system_log(
                        level="info",
                        source="system",
                        event_type="class_start",
                        message=f"수업이 시작되었습니다. ({current_time})"
                    )
                    self.last_class_check = "in_class"
            
            # 수업 종료 감지
            if current_time_obj > class_end and self.last_class_check == "in_class":
                await manager.broadcast_system_log(
                    level="info",
                    source="system",
                    event_type="class_end",
                    message=f"수업이 종료되었습니다. ({current_time})"
                )
                self.last_class_check = "after_class"
        except ValueError:
            pass

        # 점심 시간 시작/종료 감지
        try:
            lunch_start = datetime.strptime(config.LUNCH_START_TIME, "%H:%M").time()
            lunch_end = datetime.strptime(config.LUNCH_END_TIME, "%H:%M").time()

            # 점심 시간인지 확인 (시작 시간 이상, 종료 시간 미만)
            is_lunch_time = lunch_start <= current_time_obj < lunch_end

            # 점심 시작 감지
            if is_lunch_time and self.last_lunch_check != "in_lunch":
                self.last_lunch_check = "in_lunch"
                await manager.broadcast_system_log(
                    level="info",
                    source="system",
                    event_type="lunch_start",
                    message=f"점심 시간이 시작되었습니다. ({current_time})"
                )

            # 점심 종료 감지 (시작 로그 유무와 무관하게 하루 1회만 리셋)
            if current_time_obj >= lunch_end and self.last_lunch_check != "after_lunch":
                from database.db_service import utcnow
                await self.db_service.reset_camera_off_timers(utcnow(), joined_student_ids=None)
                self.last_lunch_check = "after_lunch"
                await manager.broadcast_system_log(
                    level="info",
                    source="system",
                    event_type="lunch_end",
                    message=f"점심 시간이 종료되었습니다. ({current_time})"
                )
        except ValueError:
            pass

    async def _check_not_joined_students(self, joined_today: set[int]):
        """수업 시작 이후 미접속 학생을 미접속 상태로 표시"""
        if not self.slack_listener:
            return

        students = await self.db_service.get_all_students()
        updated = 0

        for student in students:
            if student.is_admin:
                continue

            if student.status_type == "not_joined":
                if student.id in joined_today:
                    if await self.db_service.clear_not_joined_status(student.id):
                        updated += 1
                continue

            if student.status_type is not None:
                continue

            if student.is_absent:
                continue

            if student.id in joined_today:
                continue

            if await self.db_service.set_not_joined_status(student.id):
                updated += 1

        if updated:
            await self.broadcast_dashboard_update_now()
    
    async def _check_students(self):
        """학생들의 카메라 상태 체크"""
        now_utc = datetime.now(timezone.utc)
        now_local = now_seoul()
        current_time_obj = now_local.time()

        await self._check_daily_reset(now_local)
        await self._check_scheduled_status()

        # 수업/점심 시간 이벤트 체크 (모니터링 활성화 여부와 무관)
        await self._check_schedule_events(now_local)

        # Slack 히스토리 복원 중에는 알림 체크를 건너뜀
        if self.slack_listener and self.slack_listener.is_restoring:
            return

        # 모니터링 활성화 체크
        if not self.is_monitoring_active():
            return

        # 워밍업 시간 체크
        if self.start_time:
            elapsed = (now_utc - self.start_time).total_seconds() / 60
            if elapsed < self.warmup_minutes:
                return

        # 수업 시간 체크
        is_class_time = self._is_class_time()
        if not is_class_time:
            return

        # 점심 시간인지 확인 (시간 객체로 비교)
        try:
            lunch_start = datetime.strptime(config.LUNCH_START_TIME, "%H:%M").time()
            lunch_end = datetime.strptime(config.LUNCH_END_TIME, "%H:%M").time()
            is_lunch_time = lunch_start <= current_time_obj < lunch_end
            if is_lunch_time:
                return
        except ValueError:
            pass

        joined_today = self.slack_listener.get_joined_students_today() if self.slack_listener else set()

        await self._check_not_joined_students(joined_today)
        
        await self._check_left_students()
        
        await self._check_return_requests()

        students = await self.db_service.get_students_camera_off_too_long(
            self.camera_off_threshold,
            self.reset_time
        )

        if not students:
            return

        candidate_students = []

        # 수업 시작 시간 계산 (수업 시작 전 입장한 학생은 수업 시작 시간부터 카운트)
        class_start_time_utc = None
        try:
            class_start = datetime.strptime(config.CLASS_START_TIME, "%H:%M").time()
            today_seoul = now_seoul().date()
            class_start_dt = datetime.combine(today_seoul, class_start)
            class_start_dt_seoul = class_start_dt.replace(tzinfo=SEOUL_TZ)
            class_start_time_utc = class_start_dt_seoul.astimezone(timezone.utc)
        except:
            pass

        for student in students:
            if not student.discord_id:
                continue

            # DB의 is_admin 필드로 관리자 확인 (Discord 봇 관리자 권한과 별개)
            if student.is_admin:
                continue

            if student.id not in joined_today:
                continue

            if student.last_leave_time is not None:
                continue

            # status_type이 있으면 (지각, 외출, 조퇴, 휴가, 결석, 미접속) 알림 보내지 않음
            if student.status_type in ['late', 'leave', 'early_leave', 'vacation', 'absence', 'not_joined']:
                continue

            if student.is_absent:
                continue

            # 알람 차단 상태 확인
            is_blocked = await self.db_service.is_alarm_blocked(student.id)
            if is_blocked:
                continue

            # 수업 시작 전에 입장한 학생은 수업 시작 시간부터 카운트
            if class_start_time_utc and student.last_status_change:
                last_change_utc = student.last_status_change if student.last_status_change.tzinfo else student.last_status_change.replace(tzinfo=timezone.utc)
                # 학생이 수업 시작 전에 입장했고, 현재 시간이 수업 시작 이후라면
                if last_change_utc < class_start_time_utc and now_utc >= class_start_time_utc:
                    # 수업 시작 시간부터 경과 시간 계산
                    elapsed_from_class_start = int((now_utc - class_start_time_utc).total_seconds() / 60)
                    # 임계값을 넘지 않았으면 제외
                    if elapsed_from_class_start < self.camera_off_threshold:
                        continue

            candidate_students.append(student)

        if not candidate_students:
            return

        student_ids = [s.id for s in candidate_students]
        alert_status = await self.db_service.should_send_alert_batch(student_ids, self.alert_cooldown)

        students_to_alert = [s for s in candidate_students if alert_status.get(s.id, False)]

        if not students_to_alert:
            return
        
        for student in students_to_alert:

            if self.is_dm_paused:
                continue

            if not student.last_status_change:
                continue

            last_change_utc = student.last_status_change if student.last_status_change.tzinfo else student.last_status_change.replace(tzinfo=timezone.utc)
            elapsed_minutes = int((now_utc - last_change_utc).total_seconds() / 60)

            if student.alert_count == 0:
                # 첫 번째 알림: 수강생에게만
                success = await self.discord_bot.send_camera_alert(student)

                # 전송 성공/실패와 관계없이 쿨타임 적용
                await self.db_service.record_alert_sent(student.id)

                if success:
                    await manager.broadcast_new_alert(
                        alert_id=0,
                        student_id=student.id,
                        zep_name=student.zep_name,
                        alert_type='camera_off_exceeded',
                        alert_message=f'{student.zep_name}님의 카메라가 {elapsed_minutes}분째 꺼져 있습니다.'
                    )
                    # DM 전송 로그
                    await manager.broadcast_system_log(
                        level="info",
                        source="discord",
                        event_type="dm_sent",
                        message=f"DM 전송: {student.zep_name}님에게 카메라 OFF 알림 ({elapsed_minutes}분 경과)",
                        student_name=student.zep_name,
                        student_id=student.id
                    )
            else:
                # 두 번째 알림부터: 수강생과 관리자 둘 다
                await self.discord_bot.send_camera_alert(student)
                await self.discord_bot.send_camera_alert_to_admin(student)

                # 알림 발송 즉시 DB 업데이트 (쿨타임 적용)
                await self.db_service.record_alert_sent(student.id)

                await manager.broadcast_new_alert(
                    alert_id=0,
                    student_id=student.id,
                    zep_name=student.zep_name,
                    alert_type='camera_off_admin',
                    alert_message=f'{student.zep_name}님의 카메라가 {elapsed_minutes}분째 꺼져 있습니다. (수강생+관리자 알림)'
                )
                # 수강생 + 관리자 알림 로그
                await manager.broadcast_system_log(
                    level="warning",
                    source="discord",
                    event_type="dm_sent",
                    message=f"DM 전송: {student.zep_name}님에게 카메라 OFF 알림 + 관리자 알림 ({elapsed_minutes}분 경과)",
                    student_name=student.zep_name,
                    student_id=student.id
                )
        
    async def _check_left_students(self):
        """접속 종료 후 복귀하지 않은 학생들 체크"""
        now_utc = datetime.now(timezone.utc)
        students = await self.db_service.get_students_left_too_long(
            self.leave_alert_threshold
        )
        
        if not students:
            return
        
        joined_today = self.slack_listener.get_joined_students_today() if self.slack_listener else set()
        
        non_absent_candidates = []
        absent_candidates = []

        for student in students:
            if student.discord_id and self.discord_bot.is_admin(student.discord_id):
                continue

            if student.id not in joined_today:
                continue

            if self.is_dm_paused:
                continue

            # status_type이 있으면 (지각, 외출, 조퇴, 휴가, 결석, 미접속) 알림 보내지 않음
            if student.status_type in ['late', 'leave', 'early_leave', 'vacation', 'absence', 'not_joined']:
                continue

            if not student.is_absent:
                non_absent_candidates.append(student)
            else:
                if student.discord_id:
                    absent_candidates.append(student)
        
        if non_absent_candidates:
            student_ids = [s.id for s in non_absent_candidates]
            alert_status = await self.db_service.should_send_leave_admin_alert_batch(student_ids, self.leave_admin_alert_cooldown)
            
            students_to_alert = [s for s in non_absent_candidates if alert_status.get(s.id, False)]
            alerted_ids = []
            
            for student in students_to_alert:
                if not student.last_leave_time:
                    continue

                await self.discord_bot.send_leave_alert_to_admin(student)
                alerted_ids.append(student.id)

                last_leave_time_utc = student.last_leave_time if student.last_leave_time.tzinfo else student.last_leave_time.replace(tzinfo=timezone.utc)
                elapsed_minutes = int((now_utc - last_leave_time_utc).total_seconds() / 60)
                
                await manager.broadcast_new_alert(
                    alert_id=0,
                    student_id=student.id,
                    zep_name=student.zep_name,
                    alert_type='leave_alert',
                    alert_message=f'{student.zep_name}님이 접속을 종료한 지 {elapsed_minutes}분이 지났습니다.'
                )
                # 관리자 접속 종료 알림 로그
                await manager.broadcast_system_log(
                    level="warning",
                    source="discord",
                    event_type="dm_sent",
                    message=f"관리자 알림: {student.zep_name}님 접속 종료 ({elapsed_minutes}분 경과)",
                    student_name=student.zep_name,
                    student_id=student.id
                )
            
            if alerted_ids:
                await self.db_service.record_leave_admin_alerts_sent_batch(alerted_ids)
        
        for student in absent_candidates:
            should_alert = await self.db_service.should_send_absent_alert(
                student.id,
                self.absent_alert_cooldown
            )
            
            if should_alert:
                success = await self.discord_bot.send_absent_alert(student)

                # 전송 성공/실패와 관계없이 쿨타임 적용
                await self.db_service.record_absent_alert_sent(student.id)

                if success:
                    if not student.last_leave_time:
                        continue

                    last_leave_time_utc = student.last_leave_time if student.last_leave_time.tzinfo else student.last_leave_time.replace(tzinfo=timezone.utc)
                    elapsed_minutes = int((now_utc - last_leave_time_utc).total_seconds() / 60)
                    absent_type_text = "외출" if student.absent_type == "leave" else "조퇴"
                    
                    await manager.broadcast_new_alert(
                        alert_id=0,
                        student_id=student.id,
                        zep_name=student.zep_name,
                        alert_type='absent_alert',
                        alert_message=f'{student.zep_name}님 {absent_type_text} 확인 - 접속 종료 후 {elapsed_minutes}분 경과'
                    )
                    # 외출/조퇴 알림 DM 전송 로그
                    await manager.broadcast_system_log(
                        level="warning",
                        source="discord",
                        event_type="dm_sent",
                        message=f"DM 전송: {student.zep_name}님에게 {absent_type_text} 알림 ({elapsed_minutes}분 경과)",
                        student_name=student.zep_name,
                        student_id=student.id
                    )
    
    async def _check_return_requests(self):
        """복귀 요청 후 접속하지 않은 학생들 체크"""
        students = await self.db_service.get_students_with_return_request(
            self.return_reminder_time
        )

        if not students:
            return

        for student in students:
            if not student.discord_id:
                continue

            if self.discord_bot.is_admin(student.discord_id):
                continue

            if self.is_dm_paused:
                continue

            # status_type이 있으면 (지각, 외출, 조퇴, 휴가, 결석, 미접속) 알림 보내지 않음
            if student.status_type in ['late', 'leave', 'early_leave', 'vacation', 'absence', 'not_joined']:
                continue

            success = await self.discord_bot.send_return_reminder(student)

            # 전송 성공/실패와 관계없이 쿨타임 적용
            await self.db_service.record_return_request(student.id)

            if success:
                # 복귀 요청 DM 전송 로그
                await manager.broadcast_system_log(
                    level="info",
                    source="discord",
                    event_type="dm_sent",
                    message=f"DM 전송: {student.zep_name}님에게 복귀 요청 알림",
                    student_name=student.zep_name,
                    student_id=student.id
                )

    def _parse_daily_reset_time(self, time_str: Optional[str]) -> Optional[time]:
        """환경 변수 문자열을 time 객체로 변환"""
        if not time_str:
            return None
        try:
            return datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            print(f"⚠️ DAILY_RESET_TIME 형식이 잘못되었습니다. 'HH:MM' 형식으로 설정해주세요. (현재 값: {time_str})")
            return None

    async def _check_startup_reset(self):
        """프로그램 시작 시 일일 초기화 확인 및 실행 (재시작 시 이전 상태 복원)"""
        if not self.daily_reset_time:
            return
        
        from database.db_service import SEOUL_TZ
        now_local = now_seoul()
        today_str = now_local.strftime("%Y-%m-%d")
        scheduled_dt = datetime.combine(now_local.date(), self.daily_reset_time)
        # 서울 시간으로 설정 후 UTC로 변환
        scheduled_dt_seoul = scheduled_dt.replace(tzinfo=SEOUL_TZ)
        scheduled_dt_utc = scheduled_dt_seoul.astimezone(timezone.utc)
        
        if now_local >= scheduled_dt_seoul:
            all_students = await self.db_service.get_all_students()
            
            has_recent_students = False
            for student in all_students:
                if not student.last_status_change:
                    continue
                if student.last_status_change.tzinfo is None:
                    last_change_utc = student.last_status_change.replace(tzinfo=timezone.utc)
                else:
                    last_change_utc = student.last_status_change
                
                if last_change_utc > scheduled_dt_utc:
                    has_recent_students = True
                    break
            
            if has_recent_students:
                self.reset_time = scheduled_dt_utc
                self.last_daily_reset_date = today_str
                print(f"💾 오늘 초기화는 이미 실행되었습니다 ({scheduled_dt.strftime('%Y-%m-%d %H:%M')})")
                print("   ✅ 초기화 시간 이후 접속한 학생의 상태가 보존됩니다.")
            else:
                self.is_resetting = True
                await manager.broadcast_system_log(
                    level="info",
                    source="system",
                    event_type="daily_reset",
                    message=f"일일 초기화가 진행 중입니다. ({scheduled_dt.strftime('%Y-%m-%d %H:%M')})"
                )
                
                reset_time = await self.db_service.reset_alert_status_preserving_recent(scheduled_dt_utc)
                self.reset_time = reset_time
                self.last_daily_reset_date = today_str
                
                self.is_resetting = False
                await manager.broadcast_system_log(
                    level="success",
                    source="system",
                    event_type="daily_reset",
                    message=f"일일 초기화가 완료되었습니다. ({scheduled_dt.strftime('%Y-%m-%d %H:%M')})"
                )
        else:
            print(f"⏰ 일일 초기화 시간 전입니다 ({scheduled_dt.strftime('%H:%M')})")
            print("   💾 이전 상태를 유지합니다.")

    async def _check_scheduled_status(self):
        """예약된 상태가 있는 학생들을 체크하고 시간이 되면 자동으로 상태 적용"""
        try:
            students = await self.db_service.get_students_with_scheduled_status()

            for student in students:
                success = await self.db_service.apply_scheduled_status(student.id)
                if success:
                    print(f"📅 [예약 상태 적용] {student.zep_name}님: {student.scheduled_status_type}")
                    # 대시보드 업데이트
                    await self.broadcast_dashboard_update_now()

        except Exception as e:
            print(f"❌ [예약 상태 체크 오류] {e}")

    async def _check_daily_reset(self, now: datetime):
        """매일 지정된 시각에 알림 상태를 초기화"""
        if not self.daily_reset_time:
            return
        
        today_str = now.strftime("%Y-%m-%d")
        if self.last_daily_reset_date == today_str:
            return
        
        from database.db_service import SEOUL_TZ
        scheduled_dt = datetime.combine(now.date(), self.daily_reset_time)
        # 서울 시간으로 설정 후 UTC로 변환
        scheduled_dt_seoul = scheduled_dt.replace(tzinfo=SEOUL_TZ)
        reset_time_utc = scheduled_dt_seoul.astimezone(timezone.utc)

        if now >= scheduled_dt_seoul:
            self.is_resetting = True
            await manager.broadcast_system_log(
                level="info",
                source="system",
                event_type="daily_reset",
                message=f"일일 초기화가 진행 중입니다. ({scheduled_dt.strftime('%Y-%m-%d %H:%M')})"
            )
            reset_time = await self.db_service.reset_all_alert_status()
            self.reset_time = reset_time
            self.last_daily_reset_date = today_str

            # 날짜 기반 상태 자동 해제 (휴가/결석 등)
            await self.db_service.check_and_reset_status_by_date()

            # 오늘 접속한 학생 목록 초기화
            if self.slack_listener:
                self.slack_listener.joined_students_today.clear()

            # 일일 초기화 시 수업/점심 로그 상태도 리셋
            self.last_lunch_check = None
            self.last_class_check = None

            self.is_resetting = False

            # 대기 중인 이벤트 처리
            if self.slack_listener:
                await self.slack_listener.process_pending_events()

            await manager.broadcast_system_log(
                level="success",
                source="system",
                event_type="daily_reset",
                message=f"일일 초기화가 완료되었습니다. ({scheduled_dt.strftime('%Y-%m-%d %H:%M')})"
            )
    
    async def _get_dashboard_overview(self) -> dict:
        """대시보드 현황 데이터 수집"""
        students = await self.db_service.get_all_students()
        joined_today = self.slack_listener.get_joined_students_today() if self.slack_listener else set()
        now = datetime.now(timezone.utc)
        return build_overview(students, joined_today, now, self.camera_off_threshold)
    
    async def broadcast_dashboard_update_now(self):
        """대시보드 업데이트 즉시 브로드캐스트 (상태 변경 시 호출)"""
        try:
            overview = await self._get_dashboard_overview()
            await manager.broadcast_dashboard_update(overview)
        except Exception:
            pass
    
    async def _broadcast_dashboard_periodically(self):
        """1초마다 대시보드 현황 브로드캐스트 (상태 변경 시 즉시 업데이트되므로 백업용)"""
        while self.is_running:
            try:
                if self.is_monitoring_active():
                    overview = await self._get_dashboard_overview()
                    await manager.broadcast_dashboard_update(overview)
            except Exception:
                pass
            
            await asyncio.sleep(1)
