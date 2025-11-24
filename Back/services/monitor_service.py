"""
모니터링 서비스
주기적으로 학생들의 카메라 상태를 체크하고 알림을 전송합니다.
"""
import asyncio
from datetime import datetime, time, timezone, date
from typing import Optional

from config import config
from database import DBService
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
        self.slack_listener = None  # SlackListener는 나중에 설정됨
        self.is_running = False
        self.check_interval = config.CHECK_INTERVAL
        self.camera_off_threshold = config.CAMERA_OFF_THRESHOLD
        self.alert_cooldown = config.ALERT_COOLDOWN
        self.leave_alert_threshold = config.LEAVE_ALERT_THRESHOLD
        self.leave_admin_alert_cooldown = config.LEAVE_ADMIN_ALERT_COOLDOWN
        self.absent_alert_cooldown = config.ABSENT_ALERT_COOLDOWN
        self.return_reminder_time = config.RETURN_REMINDER_TIME
        self.start_time = None  # 서비스 시작 시간
        self.warmup_minutes = 1  # 워밍업 시간 (분) - 시작 후 이 시간 동안은 알림 보내지 않음
        self.last_lunch_check = None  # 마지막 점심 시간 체크 상태
        self.daily_reset_time = self._parse_daily_reset_time(config.DAILY_RESET_TIME)
        self.last_daily_reset_date: Optional[str] = None  # 마지막 일일 초기화 날짜 (YYYY-MM-DD)
        self.reset_time: Optional[datetime] = None  # 초기화 시간 (접속 여부 판단용)
        self.is_resetting = False  # 초기화 진행 중 플래그
        self.is_dm_paused = False  # DM 발송 일시정지 플래그
        self.is_monitoring_paused = False  # 모니터링 일시정지 플래그 (수동 제어)
        self.holiday_checker = HolidayChecker()  # 주말/공휴일 체크
    
    def set_slack_listener(self, slack_listener):
        """SlackListener 참조 설정 (순환 참조 방지)"""
        self.slack_listener = slack_listener
    
    async def start(self):
        """모니터링 시작"""
        self.is_running = True
        self.start_time = datetime.now(timezone.utc)  # 시작 시간 기록
        
        # 프로그램 시작 시 일일 초기화 확인 (재시작 시 이전 상태 복원)
        await self._check_startup_reset()
        
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
        
        # 대시보드 업데이트 태스크 시작
        asyncio.create_task(self._broadcast_dashboard_periodically())
        
        while self.is_running:
            try:
                await self._check_students()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"❌ 모니터링 체크 중 오류: {e}")
                await asyncio.sleep(self.check_interval)
    
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
        # 수동 일시정지 체크
        if self.is_monitoring_paused:
            return False
        
        # 주말/공휴일 체크
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
        now = datetime.now()
        current_time = now.time()
        
        # 수업 시작/종료 시간 파싱
        try:
            class_start = datetime.strptime(config.CLASS_START_TIME, "%H:%M").time()
            class_end = datetime.strptime(config.CLASS_END_TIME, "%H:%M").time()
            lunch_start = datetime.strptime(config.LUNCH_START_TIME, "%H:%M").time()
            lunch_end = datetime.strptime(config.LUNCH_END_TIME, "%H:%M").time()
        except ValueError as e:
            # 파싱 실패 시 기본값으로 처리
            print(f"⚠️ 시간 파싱 실패: {e}")
            return False
        
        # 수업 시작 전이면 False
        if current_time < class_start:
            return False
        
        # 수업 종료 후면 False
        if current_time > class_end:
            return False
        
        # 점심 시간이면 False
        if lunch_start <= current_time <= lunch_end:
            return False
        
        # 위 조건을 모두 통과하면 수업 시간
        return True
    
    async def _check_students(self):
        """학생들의 카메라 상태 체크"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_time_obj = now.time()
        
        # 디버깅: 수업 종료 시간 이후인지 먼저 체크 (항상 출력)
        try:
            class_end_obj = datetime.strptime(config.CLASS_END_TIME, "%H:%M").time()
            class_start_obj = datetime.strptime(config.CLASS_START_TIME, "%H:%M").time()
            if current_time_obj > class_end_obj:
                print(f"⏰ [체크] 수업 종료 시간 이후 ({current_time} > {config.CLASS_END_TIME}) - _check_students() 실행됨")
            elif current_time_obj < class_start_obj:
                print(f"⏰ [체크] 수업 시작 시간 전 ({current_time} < {config.CLASS_START_TIME}) - _check_students() 실행됨")
        except Exception as e:
            print(f"⚠️ [체크] 시간 파싱 오류: {e}")
        
        # 일일 초기화 체크 (워밍업 여부와 관계없이 실행)
        await self._check_daily_reset(now)
        
        # 모니터링 활성화 여부 체크 (주말/공휴일, 수동 일시정지)
        if not self.is_monitoring_active():
            print(f"⏸️ [체크] 모니터링 비활성화 - 스킵")
            return
        
        # 워밍업 시간 체크 (프로그램 시작 직후 알림 방지)
        if self.start_time:
            elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds() / 60
            if elapsed < self.warmup_minutes:
                print(f"⏳ [체크] 워밍업 시간 중 ({elapsed:.1f}분 < {self.warmup_minutes}분) - 스킵")
                return
        
        # 점심 시간 시작/종료 체크 및 시간 초기화
        is_lunch_time = config.LUNCH_START_TIME <= current_time <= config.LUNCH_END_TIME
        
        # 점심 시간에 진입했는지 체크 (이전 체크가 점심 시간이 아니었는데 지금은 점심 시간)
        if is_lunch_time and self.last_lunch_check != "in_lunch":
            print(f"🍽️ 점심 시간 시작 ({current_time}) - 카메라 OFF 학생들의 시간 초기화")
            lunch_start_dt = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {config.LUNCH_START_TIME}", "%Y-%m-%d %H:%M")
            await self.db_service.reset_camera_off_timers(lunch_start_dt)
            self.last_lunch_check = "in_lunch"
            print(f"   ✅ 카메라 OFF 학생들의 시간이 점심 시작 시간으로 초기화되었습니다.")
            return
        
        # 점심 시간에서 나왔는지 체크 (이전 체크가 점심 시간이었는데 지금은 점심 시간이 아님)
        if not is_lunch_time and self.last_lunch_check == "in_lunch":
            print(f"🍽️ 점심 시간 종료 ({current_time}) - 카메라 OFF 학생들의 시간 초기화")
            lunch_end_dt = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {config.LUNCH_END_TIME}", "%Y-%m-%d %H:%M")
            await self.db_service.reset_camera_off_timers(lunch_end_dt)
            self.last_lunch_check = "after_lunch"
            print(f"   ✅ 카메라 OFF 학생들의 시간이 점심 종료 시간으로 초기화되었습니다.")
            # 점심 종료 후 바로 알림 체크는 하지 않고 다음 체크에서 시작
            return
        
        # 점심 시간 중에는 알림 안 보냄
        if is_lunch_time:
            return
        
        # 수업 시간 체크 (수업 시간이 아니면 모든 알림 중단)
        is_class_time = self._is_class_time()
        if not is_class_time:
            # 수업 시간이 아니면 조용히 스킵
            now_str = now.strftime("%H:%M")
            current_time_obj = now.time()
            class_end_obj = datetime.strptime(config.CLASS_END_TIME, "%H:%M").time()
            
            # 디버깅: 수업 종료 후 알람이 오는 경우를 확인하기 위해 로그 추가
            if current_time_obj > class_end_obj:
                print(f"⏰ 수업 종료 시간 이후 ({now_str} > {config.CLASS_END_TIME}) - 알림 중단")
            elif current_time_obj < datetime.strptime(config.CLASS_START_TIME, "%H:%M").time():
                print(f"⏰ 수업 시작 시간 전 ({now_str} < {config.CLASS_START_TIME}) - 알림 중단")
            return
        
        # 접속 종료 학생 체크 (카메라 상태와 무관하게 항상 수행)
        await self._check_left_students()
        
        # 복귀 요청 모니터링
        await self._check_return_requests()
        
        # 카메라가 임계값 이상 꺼진 학생들 조회 (초기화 이후 접속한 학생만)
        students = await self.db_service.get_students_camera_off_too_long(
            self.camera_off_threshold,
            self.reset_time  # 초기화 시간 전달
        )
        
        if not students:
            return
        
        # 오늘 접속한 학생 목록 가져오기
        joined_today = self.slack_listener.get_joined_students_today() if self.slack_listener else set()
        
        print(f"🔍 카메라 OFF 임계값 초과 학생: {len(students)}명")
        
        for student in students:
            # Discord ID 확인
            if not student.discord_id:
                print(f"   ⚠️ {student.zep_name}: Discord 미등록 (등록 필요)")
                continue
            
            # 관리자 제외 (관리자는 모니터링 대상 아님)
            if self.discord_bot.is_admin(student.discord_id):
                continue
            
            # 오늘 미접속 학생 제외 (오늘 접속한 학생만 알림 전송)
            if student.id not in joined_today:
                print(f"   ⏭️ {student.zep_name}: 오늘 미접속 (알림 제외)")
                continue
            
            # 접속 종료한 학생 제외 (접속 종료 알림으로 별도 처리)
            if student.last_leave_time is not None:
                print(f"   ⏭️ {student.zep_name}: 접속 종료 상태 (접속 종료 알림으로 처리)")
                continue
            
            # 외출/조퇴 상태인 학생 제외
            if student.is_absent:
                print(f"   ⏭️ {student.zep_name}: 외출/조퇴 처리됨 (알림 중단)")
                continue
            
            # 쿨다운 체크
            should_alert = await self.db_service.should_send_alert(
                student.id,
                self.alert_cooldown
            )
            
            if not should_alert:
                continue  # 쿨다운 중이면 조용히 스킵
            
            # DM 발송 일시정지 체크
            if self.is_dm_paused:
                print(f"   🔕 {student.zep_name}: DM 발송 일시정지 중 (알림 보류)")
                continue
            
            # 경과 시간 계산
            last_change_utc = student.last_status_change if student.last_status_change.tzinfo else student.last_status_change.replace(tzinfo=timezone.utc)
            elapsed_minutes = int((datetime.now(timezone.utc) - last_change_utc).total_seconds() / 60)
            
            # 첫 번째 알림: 학생에게 DM 전송
            if student.alert_count == 0:
                print(f"   📤 {student.zep_name}에게 첫 알림 전송...")
                success = await self.discord_bot.send_camera_alert(student)
                
                if success:
                    # 알림 전송 기록
                    await self.db_service.record_alert_sent(student.id)
                    print(f"   ✅ 알림 전송 완료: {student.zep_name}")
                    
                    # WebSocket 브로드캐스트
                    await manager.broadcast_new_alert(
                        alert_id=0,  # TODO: alert 테이블 추가 후 ID 사용
                        student_id=student.id,
                        zep_name=student.zep_name,
                        alert_type='camera_off_exceeded',
                        alert_message=f'{student.zep_name}님의 카메라가 {elapsed_minutes}분째 꺼져 있습니다.'
                    )
                else:
                    print(f"   ❌ 알림 전송 실패: {student.zep_name}")
            
            # 두 번째 알림 이상: 관리자 채널에만 전송
            else:
                print(f"   📤 {student.zep_name} - 관리자 채널에 카메라 OFF 알림 전송...")
                await self.discord_bot.send_camera_alert_to_admin(student)
                await self.db_service.record_alert_sent(student.id)
                print(f"   ✅ 관리자 알림 전송 완료: {student.zep_name}")
                
                # WebSocket 브로드캐스트
                await manager.broadcast_new_alert(
                    alert_id=0,  # TODO: alert 테이블 추가 후 ID 사용
                    student_id=student.id,
                    zep_name=student.zep_name,
                    alert_type='camera_off_admin',
                    alert_message=f'{student.zep_name}님의 카메라가 {elapsed_minutes}분째 꺼져 있습니다. (관리자 알림)'
                )
        
    async def _check_left_students(self):
        """접속 종료 후 복귀하지 않은 학생들 체크"""
        # 수업 시간이 아니면 체크 안 함 (카메라 알림과 동일한 시간대 사용)
        if not self._is_class_time():
            return
        
        # 접속 종료 알림은 실시간 이벤트이므로 워밍업 시간 불필요
        # (last_leave_time은 접속 종료 시점에 기록되므로 프로그램 시작 전 데이터가 아님)
        
        # 접속 종료 후 임계값 이상 지난 학생들 조회
        students = await self.db_service.get_students_left_too_long(
            self.leave_alert_threshold
        )
        
        if not students:
            return
        
        # 오늘 접속한 학생 목록 가져오기
        joined_today = self.slack_listener.get_joined_students_today() if self.slack_listener else set()
        
        print(f"🔍 접속 종료 임계값 초과 학생: {len(students)}명")
        
        for student in students:
            # 관리자 제외 (관리자는 모니터링 대상 아님)
            if student.discord_id and self.discord_bot.is_admin(student.discord_id):
                continue
            
            # 오늘 미접속 학생 제외 (오늘 접속한 학생만 알림 전송)
            if student.id not in joined_today:
                print(f"   ⏭️ {student.zep_name}: 오늘 미접속 (알림 제외)")
                continue
            
            # DM 발송 일시정지 체크
            if self.is_dm_paused:
                print(f"   🔕 {student.zep_name}: DM 발송 일시정지 중 (알림 보류)")
                continue
            
            # 외출/조퇴 상태가 아닌 학생에게만 관리자 알림 (외출/조퇴 확인 요청)
            if not student.is_absent:
                # 관리자 알림 쿨다운 체크
                should_alert = await self.db_service.should_send_leave_admin_alert(
                    student.id,
                    self.leave_admin_alert_cooldown
                )
                
                if should_alert:
                    print(f"   📤 {student.zep_name} - 관리자에게 접속 종료 알림 전송...")
                    await self.discord_bot.send_leave_alert_to_admin(student)
                    await self.db_service.record_leave_admin_alert_sent(student.id)
                    print(f"   ✅ 관리자 알림 전송 완료: {student.zep_name}")
                    
                    # 경과 시간 계산
                    last_leave_time_utc = student.last_leave_time if student.last_leave_time.tzinfo else student.last_leave_time.replace(tzinfo=timezone.utc)
                    elapsed_minutes = int((datetime.now(timezone.utc) - last_leave_time_utc).total_seconds() / 60)
                    
                    # WebSocket 브로드캐스트
                    await manager.broadcast_new_alert(
                        alert_id=0,
                        student_id=student.id,
                        zep_name=student.zep_name,
                        alert_type='leave_alert',
                        alert_message=f'{student.zep_name}님이 접속을 종료한 지 {elapsed_minutes}분이 지났습니다.'
                    )
                else:
                    # 쿨다운 중인 경우 로그 출력
                    if student.last_leave_admin_alert:
                        last_alert_utc = student.last_leave_admin_alert if student.last_leave_admin_alert.tzinfo else student.last_leave_admin_alert.replace(tzinfo=timezone.utc)
                        elapsed = (datetime.now(timezone.utc) - last_alert_utc).total_seconds() / 60
                        print(f"   ⏳ {student.zep_name} - 관리자 알림 쿨다운 중 ({elapsed:.1f}/{self.leave_admin_alert_cooldown}분)")
            
            # 외출/조퇴 상태인 학생에게는 주기적으로 DM 전송
            if student.is_absent:
                should_alert = await self.db_service.should_send_absent_alert(
                    student.id,
                    self.absent_alert_cooldown
                )
                
                if should_alert and student.discord_id:
                    print(f"   📤 {student.zep_name}에게 외출/조퇴 알림 전송...")
                    success = await self.discord_bot.send_absent_alert(student)
                    
                    if success:
                        await self.db_service.record_absent_alert_sent(student.id)
                        print(f"   ✅ 외출/조퇴 알림 전송 완료: {student.zep_name}")
                        
                        # 경과 시간 계산
                        last_leave_time_utc = student.last_leave_time if student.last_leave_time.tzinfo else student.last_leave_time.replace(tzinfo=timezone.utc)
                        elapsed_minutes = int((datetime.now(timezone.utc) - last_leave_time_utc).total_seconds() / 60)
                        absent_type_text = "외출" if student.absent_type == "leave" else "조퇴"
                        
                        # WebSocket 브로드캐스트
                        await manager.broadcast_new_alert(
                            alert_id=0,
                            student_id=student.id,
                            zep_name=student.zep_name,
                            alert_type='absent_alert',
                            alert_message=f'{student.zep_name}님 {absent_type_text} 확인 - 접속 종료 후 {elapsed_minutes}분 경과'
                        )
                    else:
                        print(f"   ❌ 외출/조퇴 알림 전송 실패: {student.zep_name}")
    
    async def _check_return_requests(self):
        """복귀 요청 후 접속하지 않은 학생들 체크"""
        # 수업 시간이 아니면 체크 안 함
        if not self._is_class_time():
            return
        
        # 복귀 요청 후 임계값 이상 지난 학생들 조회
        students = await self.db_service.get_students_with_return_request(
            self.return_reminder_time
        )
        
        if not students:
            return
        
        print(f"🔍 복귀 요청 후 미접속 학생: {len(students)}명")
        
        for student in students:
            if not student.discord_id:
                continue
            
            # 관리자 제외 (관리자는 모니터링 대상 아님)
            if self.discord_bot.is_admin(student.discord_id):
                continue
            
            # DM 발송 일시정지 체크
            if self.is_dm_paused:
                print(f"   🔕 {student.zep_name}: DM 발송 일시정지 중 (알림 보류)")
                continue
            
            # 학생에게 복귀 재알림 DM 전송
            print(f"   📤 {student.zep_name}에게 복귀 재알림 전송...")
            success = await self.discord_bot.send_return_reminder(student)
            
            if success:
                # 복귀 요청 시간 갱신 (다음 알림을 위해)
                await self.db_service.record_return_request(student.id)
                print(f"   ✅ 복귀 재알림 전송 완료: {student.zep_name}")
            else:
                print(f"   ❌ 복귀 재알림 전송 실패: {student.zep_name}")

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
            # 일일 초기화가 비활성화된 경우 초기화 시간 없음
            return
        
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        scheduled_dt = datetime.combine(now.date(), self.daily_reset_time)
        scheduled_dt_utc = scheduled_dt.replace(tzinfo=timezone.utc)
        
        # 오늘 초기화 시간이 지났는지 확인
        if now >= scheduled_dt:
            # 오늘 초기화가 이미 실행되었는지 확인
            # 초기화 시간 이후 접속한 학생이 있는지 확인
            all_students = await self.db_service.get_all_students()
            
            # 초기화 시간 이후 접속한 학생이 있는지 확인
            has_recent_students = False
            for student in all_students:
                if student.last_status_change.tzinfo is None:
                    last_change_utc = student.last_status_change.replace(tzinfo=timezone.utc)
                else:
                    last_change_utc = student.last_status_change
                
                # 초기화 시간 이후 접속한 학생이 있으면
                if last_change_utc > scheduled_dt_utc:
                    has_recent_students = True
                    break
            
            if has_recent_students:
                # 초기화 시간 이후 접속한 학생이 있으면 → 오늘 초기화가 이미 실행된 것으로 간주
                # 초기화 시간을 저장하고 초기화는 실행하지 않음
                self.reset_time = scheduled_dt_utc
                self.last_daily_reset_date = today_str
                print(f"💾 오늘 초기화는 이미 실행되었습니다 ({scheduled_dt.strftime('%Y-%m-%d %H:%M')})")
                print("   ✅ 초기화 시간 이후 접속한 학생의 상태가 보존됩니다.")
            else:
                # 초기화 시간 이후 접속한 학생이 없으면 → 초기화가 실행되지 않았으므로 초기화 실행
                self.is_resetting = True
                print(f"🧹 프로그램 시작 시 일일 초기화 실행 ({scheduled_dt.strftime('%Y-%m-%d %H:%M')})")
                print("   ⏸️ 초기화 진행 중... (Slack 로그 처리 일시 중지)")
                print("   💾 초기화 시간 이후 접속한 학생의 상태는 보존됩니다.")
                
                # 초기화 시간 이후 접속한 학생은 상태 유지, 이전 학생만 초기화
                reset_time = await self.db_service.reset_alert_status_preserving_recent(scheduled_dt_utc)
                self.reset_time = reset_time  # 초기화 시간 저장
                self.last_daily_reset_date = today_str
                
                # 초기화 완료 플래그 해제
                self.is_resetting = False
                print("   ✅ 알림/접속 종료 상태가 초기화되었습니다. (최근 접속 학생 상태 보존)")
                print("   ▶️ Slack 로그 처리 재개")
        else:
            # 초기화 시간이 아직 안 지났으면 초기화 안 함
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
            # 초기화 시작 플래그 설정
            self.is_resetting = True
            print(f"🧹 일일 초기화 실행 ({scheduled_dt.strftime('%Y-%m-%d %H:%M')})")
            print("   ⏸️ 초기화 진행 중... (Slack 로그 처리 일시 중지)")
            
            # 정상 실행 중 초기화는 모든 학생 초기화 (이미 접속한 학생은 없음)
            reset_time_utc = scheduled_dt.replace(tzinfo=timezone.utc)
            reset_time = await self.db_service.reset_all_alert_status()
            self.reset_time = reset_time  # 초기화 시간 저장
            self.last_daily_reset_date = today_str
            
            # 초기화 완료 플래그 해제
            self.is_resetting = False
            print("   ✅ 알림/접속 종료 상태가 초기화되었습니다.")
            print("   ▶️ Slack 로그 처리 재개")
    
    async def _get_dashboard_overview(self) -> dict:
        """대시보드 현황 데이터 수집"""
        students = await self.db_service.get_all_students()
        
        now = datetime.now(timezone.utc)
        threshold_minutes = self.camera_off_threshold
        
        camera_on = 0
        camera_off = 0
        left = 0
        threshold_exceeded = 0
        
        for student in students:
            if student.last_leave_time:
                left += 1
            elif student.is_cam_on:
                camera_on += 1
            else:
                camera_off += 1
                # 임계값 초과 체크
                if student.last_status_change:
                    last_change_utc = student.last_status_change
                    if last_change_utc.tzinfo is None:
                        last_change_utc = last_change_utc.replace(tzinfo=timezone.utc)
                    elapsed = (now - last_change_utc).total_seconds() / 60
                    if elapsed >= threshold_minutes:
                        threshold_exceeded += 1
        
        return {
            "total_students": len(students),
            "camera_on": camera_on,
            "camera_off": camera_off,
            "left": left,
            "not_joined_today": 0,  # TODO: joined_today 로직
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
        """5초마다 대시보드 현황 브로드캐스트"""
        while self.is_running:
            try:
                # 모니터링이 활성화된 경우에만 대시보드 업데이트
                if self.is_monitoring_active():
                    overview = await self._get_dashboard_overview()
                    await manager.broadcast_dashboard_update(overview)
            except Exception:
                pass
            
            await asyncio.sleep(5)  # 5초마다 업데이트 (실시간성 향상)

