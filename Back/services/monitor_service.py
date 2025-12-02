"""
모니터링 서비스
주기적으로 학생들의 카메라 상태를 체크하고 알림을 전송합니다.
"""
import asyncio
from datetime import datetime, time, timezone, date
from typing import Optional

from config import config
from database import DBService
from database.db_service import now_seoul, to_utc, SEOUL_TZ
from utils.holiday_checker import HolidayChecker
from api.websocket_manager import manager


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
        
        # 점심 시간 시작/종료 감지 (수업 시간 내에서만)
        try:
            lunch_start = datetime.strptime(config.LUNCH_START_TIME, "%H:%M").time()
            lunch_end = datetime.strptime(config.LUNCH_END_TIME, "%H:%M").time()
            
            # 점심 시간인지 확인 (시작 시간 이상, 종료 시간 미만)
            is_lunch_time = lunch_start <= current_time_obj < lunch_end
            
            # 점심 시작 감지 (점심 시간에 진입했을 때)
            if is_lunch_time and self.last_lunch_check != "in_lunch":
                lunch_start_dt = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {config.LUNCH_START_TIME}", "%Y-%m-%d %H:%M")
                # 오늘 접속한 학생들만 리셋
                joined_today = self.slack_listener.get_joined_students_today() if self.slack_listener else set()
                await self.db_service.reset_camera_off_timers(lunch_start_dt, joined_student_ids=joined_today)
                self.last_lunch_check = "in_lunch"
                await manager.broadcast_system_log(
                    level="info",
                    source="system",
                    event_type="lunch_start",
                    message=f"점심 시간이 시작되었습니다. ({current_time})"
                )
            
            # 점심 종료 감지 (점심 시간에서 벗어났을 때)
            # current_time_obj >= lunch_end이면 점심 시간이 아님
            if current_time_obj >= lunch_end and self.last_lunch_check == "in_lunch":
                lunch_end_dt = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {config.LUNCH_END_TIME}", "%Y-%m-%d %H:%M")
                # 오늘 접속한 학생들만 리셋
                joined_today = self.slack_listener.get_joined_students_today() if self.slack_listener else set()
                await self.db_service.reset_camera_off_timers(lunch_end_dt, joined_student_ids=joined_today)
                self.last_lunch_check = "after_lunch"
                await manager.broadcast_system_log(
                    level="info",
                    source="system",
                    event_type="lunch_end",
                    message=f"점심 시간이 종료되었습니다. ({current_time})"
                )
        except ValueError:
            pass
    
    async def _check_students(self):
        """학생들의 카메라 상태 체크"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_time_obj = now.time()
        
        # 함수 진입 확인용 로그 (매번 출력하면 너무 많으니 간헐적으로)
        # 실제로는 조건 체크 로그로 대체
        
        await self._check_daily_reset(now)
        
        # 수업/점심 시간 이벤트 체크 (모니터링 활성화 여부와 무관)
        await self._check_schedule_events(now)
        
        # 모니터링 활성화 체크
        if not self.is_monitoring_active():
            return
        
        # 워밍업 시간 체크
        if self.start_time:
            elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds() / 60
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
        
        await self._check_left_students()
        
        await self._check_return_requests()
        
        students = await self.db_service.get_students_camera_off_too_long(
            self.camera_off_threshold,
            self.reset_time
        )
        
        if not students:
            return
        
        joined_today = self.slack_listener.get_joined_students_today() if self.slack_listener else set()
        
        candidate_students = []
        for student in students:
            if not student.discord_id:
                continue

            if self.discord_bot.is_admin(student.discord_id):
                continue

            if student.id not in joined_today:
                continue

            if student.last_leave_time is not None:
                continue

            # status_type이 있으면 (지각, 외출, 조퇴, 휴가, 결석) 알림 보내지 않음
            if student.status_type in ['late', 'leave', 'early_leave', 'vacation', 'absence']:
                continue

            if student.is_absent:
                continue

            # 알람 차단 상태 확인
            is_blocked = await self.db_service.is_alarm_blocked(student.id)
            if is_blocked:
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
            
            last_change_utc = student.last_status_change if student.last_status_change.tzinfo else student.last_status_change.replace(tzinfo=timezone.utc)
            elapsed_minutes = int((datetime.now(timezone.utc) - last_change_utc).total_seconds() / 60)
            
            if student.alert_count == 0:
                # 첫 번째 알림: 수강생에게만
                success = await self.discord_bot.send_camera_alert(student)

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
        
        if students_to_alert:
            alerted_ids = [s.id for s in students_to_alert]
            await self.db_service.record_alerts_sent_batch(alerted_ids)
        
    async def _check_left_students(self):
        """접속 종료 후 복귀하지 않은 학생들 체크"""
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

            # status_type이 있으면 (지각, 외출, 조퇴, 휴가, 결석) 알림 보내지 않음
            if student.status_type in ['late', 'leave', 'early_leave', 'vacation', 'absence']:
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
                await self.discord_bot.send_leave_alert_to_admin(student)
                alerted_ids.append(student.id)
                
                last_leave_time_utc = student.last_leave_time if student.last_leave_time.tzinfo else student.last_leave_time.replace(tzinfo=timezone.utc)
                elapsed_minutes = int((datetime.now(timezone.utc) - last_leave_time_utc).total_seconds() / 60)
                
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
                
                if success:
                    await self.db_service.record_absent_alert_sent(student.id)
                    
                    last_leave_time_utc = student.last_leave_time if student.last_leave_time.tzinfo else student.last_leave_time.replace(tzinfo=timezone.utc)
                    elapsed_minutes = int((datetime.now(timezone.utc) - last_leave_time_utc).total_seconds() / 60)
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

            # status_type이 있으면 (지각, 외출, 조퇴, 휴가, 결석) 알림 보내지 않음
            if student.status_type in ['late', 'leave', 'early_leave', 'vacation', 'absence']:
                continue

            success = await self.discord_bot.send_return_reminder(student)
            
            if success:
                await self.db_service.record_return_request(student.id)
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
        
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        scheduled_dt = datetime.combine(now.date(), self.daily_reset_time)
        scheduled_dt_utc = scheduled_dt.replace(tzinfo=timezone.utc)
        
        if now >= scheduled_dt:
            all_students = await self.db_service.get_all_students()
            
            has_recent_students = False
            for student in all_students:
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
    
    async def _check_daily_reset(self, now: datetime):
        """매일 지정된 시각에 알림 상태를 초기화"""
        if not self.daily_reset_time:
            return
        
        today_str = now.strftime("%Y-%m-%d")
        if self.last_daily_reset_date == today_str:
            return
        
        scheduled_dt = datetime.combine(now.date(), self.daily_reset_time)
        if now >= scheduled_dt:
            self.is_resetting = True
            await manager.broadcast_system_log(
                level="info",
                source="system",
                event_type="daily_reset",
                message=f"일일 초기화가 진행 중입니다. ({scheduled_dt.strftime('%Y-%m-%d %H:%M')})"
            )
            
            reset_time_utc = scheduled_dt.replace(tzinfo=timezone.utc)
            reset_time = await self.db_service.reset_all_alert_status()
            self.reset_time = reset_time
            self.last_daily_reset_date = today_str
            
            # 날짜 기반 상태 자동 해제 (휴가/결석 등)
            await self.db_service.check_and_reset_status_by_date()

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
    
    def _is_not_joined(self, student, joined_today: set, now: datetime) -> bool:
        """
        특이사항(미접속) 여부 판단

        조건:
        1. 휴가, 결석 상태인 학생은 특이사항으로 분류
        2. 외출, 조퇴는 퇴장(left)으로 분류
        3. 초기화 후 실제 입장 이벤트가 없었던 학생은 특이사항

        Args:
            student: Student 객체
            joined_today: 오늘 접속한 학생 ID 집합
            now: 현재 시간 (UTC)

        Returns:
            특이사항이면 True
        """
        # 관리자는 제외
        if student.is_admin:
            return False

        # 외출, 조퇴, 휴가, 결석, 지각 등 status_type이 있으면 무조건 특이사항
        if student.status_type in ['leave', 'early_leave', 'vacation', 'absence', 'late']:
            return True

        # joined_today에 포함되어 있으면 접속한 것으로 간주 (특이사항 아님)
        if student.id in joined_today:
            return False

        # joined_today에 없으면 특이사항
        # joined_today는 슬랙 동기화 시 실제로 오늘 입장 이벤트가 있었던 학생들만 포함됨
        return True
    
    async def _get_dashboard_overview(self) -> dict:
        """대시보드 현황 데이터 수집"""
        students = await self.db_service.get_all_students()
        
        now = datetime.now(timezone.utc)
        threshold_minutes = self.camera_off_threshold
        
        camera_on = 0
        camera_off = 0
        left = 0
        not_joined = 0
        threshold_exceeded = 0
        
        non_admin_students = [s for s in students if not s.is_admin]
        joined_today = self.slack_listener.get_joined_students_today() if self.slack_listener else set()
        today = date.today()
        
        from zoneinfo import ZoneInfo
        
        for student in non_admin_students:
            # 상태(status_type)가 있는 사람은 특이사항에만 포함 (카메라, 퇴장에서 제외)
            has_status = student.status_type in ['late', 'leave', 'early_leave', 'vacation', 'absence']

            # 1. 특이사항 체크
            is_not_joined = self._is_not_joined(student, joined_today, now)
            if is_not_joined:
                not_joined += 1

            # 2. 퇴장 체크 (상태가 있는 사람 제외)
            if not has_status and student.last_leave_time:
                leave_time = student.last_leave_time
                if leave_time.tzinfo is None:
                    leave_time_utc = leave_time.replace(tzinfo=timezone.utc)
                else:
                    leave_time_utc = leave_time
                leave_time_local = leave_time_utc.astimezone(ZoneInfo("Asia/Seoul"))
                leave_date = leave_time_local.date()

                # 오늘 퇴장한 학생
                if leave_date == today:
                    left += 1

            # 3. 카메라 상태 체크 (입장한 사람 중 상태가 없고 퇴장하지 않은 사람만)
            if not has_status and student.id in joined_today and not student.last_leave_time:
                if student.is_cam_on:
                    camera_on += 1
                else:
                    camera_off += 1
                    if student.last_status_change:
                        last_change_utc = student.last_status_change
                        if last_change_utc.tzinfo is None:
                            last_change_utc = last_change_utc.replace(tzinfo=timezone.utc)
                        elapsed = (now - last_change_utc).total_seconds() / 60
                        if elapsed >= threshold_minutes:
                            threshold_exceeded += 1
        
        return {
            "total_students": len(non_admin_students),
            "camera_on": camera_on,
            "camera_off": camera_off,
            "left": left,
            "not_joined_today": not_joined,
            "threshold_exceeded": threshold_exceeded,
            "last_updated": now.isoformat()
        }
    
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

