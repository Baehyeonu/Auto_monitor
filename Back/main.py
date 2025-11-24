"""
ZEP 학생 모니터링 시스템 (Slack Socket Mode)
메인 엔트리 포인트 - 모든 서비스를 통합하여 실행
"""
import asyncio
import signal
import sys
from datetime import datetime, timezone, date
from typing import Optional
import uvicorn

from config import config
from database import init_db, DBService
from services.admin_manager import admin_manager
from services import SlackListener, DiscordBot, MonitorService
from services.screen_monitor import ScreenMonitor
from api.server import app
from api.websocket_manager import manager


# 전역 시스템 인스턴스 (API에서 접근하기 위해)
_system_instance: Optional['ZepMonitoringSystem'] = None

def get_system_instance() -> Optional['ZepMonitoringSystem']:
    """전역 시스템 인스턴스 반환"""
    return _system_instance


class ZepMonitoringSystem:
    """ZEP 모니터링 시스템 메인 클래스"""
    
    def __init__(self):
        """시스템 초기화"""
        global _system_instance
        _system_instance = self
        
        self.discord_bot = None
        self.slack_listener = None
        self.monitor_service = None
        self.screen_monitor = None
        self.tasks = []
        self.is_running = False
        self.is_shutting_down = False  # 종료 중 플래그
        
        # WebSocket 매니저 참조 저장 (다른 서비스에서 사용)
        self.ws_manager = manager
    
    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        """
        datetime을 UTC timezone-aware로 변환
        
        Args:
            dt: datetime 객체 (aware 또는 naive)
            
        Returns:
            UTC timezone-aware datetime
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    
    async def initialize(self):
        """모든 서비스 초기화"""
        print("=" * 60)
        print("🚀 ZEP Student Monitoring System (Slack Socket Mode)")
        print("=" * 60)
        
        # 1. 데이터베이스 초기화
        print("📊 데이터베이스 초기화 중...")
        try:
            await init_db()
            await admin_manager.refresh()
            print("✅ 데이터베이스 초기화 완료")
        except Exception as e:
            print(f"❌ 데이터베이스 초기화 실패: {e}")
            raise
        
        # 2. Discord Bot 초기화
        print("🤖 Discord Bot 초기화 중...")
        try:
            self.discord_bot = DiscordBot()
            print("✅ Discord Bot 생성 완료")
        except Exception as e:
            print(f"❌ Discord Bot 초기화 실패: {e}")
            raise
        
        # 3. Monitor Service 초기화 (먼저 생성 - SlackListener가 참조)
        print("👀 Monitor Service 초기화 중...")
        try:
            self.monitor_service = MonitorService(self.discord_bot)
            # DiscordBot에 MonitorService 참조 설정 (순환 참조 해결)
            self.discord_bot.set_monitor_service(self.monitor_service)
            print("✅ Monitor Service 생성 완료")
        except Exception as e:
            print(f"❌ Monitor Service 초기화 실패: {e}")
            raise
        
        # 4. Slack Listener 초기화 (MonitorService 참조 전달)
        print("💬 Slack Listener 초기화 중...")
        try:
            self.slack_listener = SlackListener(self.monitor_service)
            # MonitorService에 SlackListener 참조 설정 (순환 참조 해결)
            self.monitor_service.set_slack_listener(self.slack_listener)
            print("✅ Slack Listener 생성 완료")
        except Exception as e:
            print(f"❌ Slack Listener 초기화 실패: {e}")
            raise
        
        # 5. Screen Monitor 초기화 (선택적)
        if config.SCREEN_MONITOR_ENABLED:
            print("👁️ Screen Monitor 초기화 중...")
            try:
                self.screen_monitor = ScreenMonitor(self.discord_bot)
                print("✅ Screen Monitor 생성 완료")
            except Exception as e:
                print(f"❌ Screen Monitor 초기화 실패: {e}")
                print("   ⚠️ 화면 모니터링 없이 계속 진행합니다.")
                self.screen_monitor = None
        
        print("=" * 60)
        print("✅ 모든 서비스 초기화 완료")
        print("=" * 60)
        
        self.is_running = True
    
    async def start(self):
        """모든 서비스 시작"""
        print("\n🚀 시스템 시작 중...\n")
        
        try:
            # Discord Bot 시작 (백그라운드)
            discord_task = asyncio.create_task(
                self.discord_bot.start(config.DISCORD_BOT_TOKEN)
            )
            self.tasks.append(discord_task)
            
            # Discord Bot이 준비될 때까지 대기 (약간의 대기 시간 필요)
            print("⏳ Discord Bot 연결 중...")
            await asyncio.sleep(3)  # Bot이 시작할 시간을 줌
            await self.discord_bot.wait_until_ready()
            print(f"✅ Discord Bot 준비 완료: {self.discord_bot.user.name}#{self.discord_bot.user.discriminator}")
            
            # 관리자 정보 출력
            await self._print_admin_info()
            
            # Slack Listener 시작 (백그라운드)
            slack_task = asyncio.create_task(self.slack_listener.start())
            self.tasks.append(slack_task)
            
            # 잠시 대기 (Slack 연결 안정화)
            await asyncio.sleep(2)
            print("✅ Slack 연결 완료 (Socket Mode)")
            
            # Monitor Service 시작 (백그라운드)
            monitor_task = asyncio.create_task(self.monitor_service.start())
            self.tasks.append(monitor_task)
            
            # Screen Monitor 시작 (선택적)
            if self.screen_monitor:
                screen_task = asyncio.create_task(self.screen_monitor.start())
                self.tasks.append(screen_task)
            
            # API 서버 시작 (백그라운드)
            api_config = uvicorn.Config(
                app,
                host="0.0.0.0",
                port=8000,
                log_level="info"
            )
            api_server = uvicorn.Server(api_config)
            api_task = asyncio.create_task(api_server.serve())
            self.tasks.append(api_task)
            
            print("🌐 API 서버 시작 (http://localhost:8000)")
            print("🔌 WebSocket 엔드포인트: ws://localhost:8000/ws")
            print("   📚 API 문서: http://localhost:8000/docs")
            
            # 상태 출력
            self._print_status()
            
            # 키보드 입력 핸들러 시작 (터미널 단축키)
            input_task = asyncio.create_task(self._handle_keyboard_input())
            self.tasks.append(input_task)
            
            # 메인 루프: is_running이 False가 될 때까지 대기
            try:
                while self.is_running:
                    await asyncio.sleep(1)
                    # 태스크 중 하나라도 완료되면 확인
                    for task in self.tasks:
                        if task.done():
                            try:
                                await task
                            except Exception as e:
                                # 예외는 무시하고 계속
                                pass
            except Exception as e:
                # 예외 발생 시에도 종료 처리
                if self.is_running:
                    print(f"\n❌ 메인 루프 오류: {e}")
            
        except KeyboardInterrupt:
            print("\n⚠️ 사용자 중단 (Ctrl+C)")
        except Exception as e:
            print(f"\n❌ 시스템 오류: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """시스템 종료"""
        # 이미 종료 중이면 중복 호출 방지
        if self.is_shutting_down:
            return
        
        if not self.is_running:
            return
        
        self.is_shutting_down = True
        
        print("\n" + "=" * 60)
        print("🛑 시스템 종료 중...")
        print("=" * 60)
        
        self.is_running = False
        
        # Screen Monitor 중지
        if self.screen_monitor:
            try:
                await self.screen_monitor.stop()
            except Exception:
                pass
        
        # Monitor Service 중지
        if self.monitor_service:
            try:
                await self.monitor_service.stop()
            except Exception:
                pass
        
        # Slack Listener 중지
        if self.slack_listener:
            try:
                await self.slack_listener.stop()
            except Exception:
                pass
        
        # Discord Bot 종료
        if self.discord_bot:
            try:
                await self.discord_bot.close()
                print("🤖 Discord Bot 종료")
            except Exception:
                pass
        
        # 모든 태스크 취소 (안전하게)
        cancelled_tasks = []
        for task in self.tasks:
            if not task.done():
                task.cancel()
                cancelled_tasks.append(task)
        
        # 취소 완료 대기 (예외 무시)
        if cancelled_tasks:
            try:
                await asyncio.gather(*cancelled_tasks, return_exceptions=True)
            except Exception:
                pass
        
        print("=" * 60)
        print("✅ 모든 서비스가 정상적으로 종료되었습니다.")
        print("=" * 60)
    
    async def _print_admin_info(self):
        """관리자 정보 출력"""
        admin_ids = admin_manager.get_ids()
        if admin_ids:
            print(f"👑 관리자: {len(admin_ids)}명")
            for admin_id in admin_ids:
                try:
                    user = await self.discord_bot.fetch_user(admin_id)
                    print(f"   • {user.name}#{user.discriminator} (ID: {admin_id})")
                except Exception as e:
                    print(f"   • ID: {admin_id} (사용자 정보 조회 실패: {e})")
        else:
            print("⚠️ 관리자가 설정되지 않았습니다 (모든 사용자가 관리자 권한 보유)")
    
    def _print_status(self):
        """시스템 상태 출력"""
        print("\n📊 시스템 상태:")
        print(f"  • Discord Bot: {'🟢 연결됨' if self.discord_bot.is_ready else '🔴 끊김'}")
        print(f"  • Slack Listener: 🟢 Socket Mode 활성화")
        print(f"  • Monitor Service: 🟢 활성화 (체크 간격: {config.CHECK_INTERVAL}초)")
        if self.screen_monitor:
            print(f"  • Screen Monitor: 🟢 활성화 (체크 간격: {config.SCREEN_CHECK_INTERVAL}초 / {config.SCREEN_CHECK_INTERVAL//60}분)")
        else:
            print(f"  • Screen Monitor: 🔴 비활성화")
        print(f"  • 카메라 OFF 임계값: {config.CAMERA_OFF_THRESHOLD}분")
        print(f"  • 알림 쿨다운: {config.ALERT_COOLDOWN}분")
        
        # DM 발송 상태
        dm_status = "⏸️  일시정지" if self.monitor_service.is_dm_paused else "🔔 정상"
        print(f"  • DM 발송: {dm_status}")
        
        # 모니터링 상태
        if self.monitor_service.is_monitoring_paused:
            print(f"  • 모니터링: ⏸️  일시정지 (수동)")
        else:
            today = date.today()
            checker = self.monitor_service.holiday_checker
            if checker.is_weekend_or_holiday(today):
                reason = "주말" if checker.is_weekend(today) else "공휴일"
                print(f"  • 모니터링: ⏸️  일시정지 ({reason})")
            else:
                print(f"  • 모니터링: 🟢 활성화")
        
        print("\n💡 시스템이 정상적으로 실행 중입니다.")
        print("💡 단축키: [Enter] - 상태 확인, [o+Enter] - OFF 학생만, [l+Enter] - 접속 종료 학생만, [n+Enter] - 접속 안 한 학생만, [p+Enter] - DM 일시정지, [r+Enter] - DM 재개, [q+Enter] - 종료")
        print("=" * 60)
        print()
    
    async def _handle_keyboard_input(self):
        """키보드 입력 핸들러 (터미널 단축키)"""
        import threading
        import queue
        
        # 명령어 큐
        command_queue = queue.Queue()
        
        def input_thread():
            """별도 스레드에서 입력 대기"""
            while self.is_running:
                try:
                    line = input()
                    if line.strip() and self.is_running:
                        command_queue.put(line.strip())
                except (EOFError, KeyboardInterrupt):
                    break
                except Exception:
                    # 오류 발생 시 조용히 계속
                    pass
        
        # 백그라운드 스레드 시작
        thread = threading.Thread(target=input_thread, daemon=True)
        thread.start()
        
        # 큐에서 명령어를 가져와서 처리
        while self.is_running:
            try:
                # 큐에 명령어가 있는지 확인 (논블로킹)
                try:
                    command = command_queue.get_nowait()
                    await self._process_command(command)
                except queue.Empty:
                    pass
                
                await asyncio.sleep(0.1)  # CPU 사용량 줄이기
            except Exception as e:
                # 오류 발생 시 조용히 계속
                await asyncio.sleep(1)
    
    async def _process_command(self, command: str):
        """명령어 처리"""
        command = command.lower().strip()
        
        if command == 'q' or command == 'quit':
            print("\n⚠️ 종료 요청 수신")
            # shutdown()을 직접 호출하지 않고 is_running을 False로 설정
            # 메인 루프가 종료되도록 함
            self.is_running = False
            return
        
        if command == '' or command == 's' or command == 'status':
            await self._print_student_status()
            return
        
        if command == 'o' or command == 'off':
            await self._print_off_students()
            return
        
        if command == 'l' or command == 'leave':
            await self._print_left_students()
            return
        
        if command == 'n' or command == 'not_joined':
            await self._print_not_joined_students()
            return
        
        if command == 'p' or command == 'pause':
            self.monitor_service.pause_dm()
            return
        
        if command == 'r' or command == 'resume':
            self.monitor_service.resume_dm()
            return
        
        if command == 'h' or command == 'help':
            self._print_help()
            return
    
    async def _print_student_status(self):
        """학생 상태 출력 (카메라 ON/OFF, 퇴장)"""
        try:
            all_students = await DBService.get_all_students()
            
            if not all_students:
                print("\n📊 등록된 학생이 없습니다.")
                return
            
            # 오늘 입장한 학생 목록 가져오기
            joined_today = self.slack_listener.get_joined_students_today()
            
            # 상태별 분류
            camera_on = []
            camera_off = []
            left_students = []
            not_connected = []
            
            for student in all_students:
                # 관리자는 카운팅에서 제외
                if student.discord_id and self.discord_bot.is_admin(student.discord_id):
                    continue
                
                if student.last_leave_time:
                    # 접속 종료한 학생
                    left_students.append(student)
                elif student.is_cam_on:
                    camera_on.append(student)
                else:
                    # 카메라 OFF - 오늘 입장했는지 확인
                    if student.id in joined_today:
                        # 오늘 입장했는데 카메라 OFF
                        camera_off.append(student)
                    else:
                        # 오늘 입장 안 함
                        not_connected.append(student)
            
            # 현재 시간 (표시용은 로컬 시간, 계산용은 UTC)
            now_local = datetime.now()
            now_utc = datetime.now(timezone.utc)
            current_time = now_local.strftime("%Y-%m-%d %H:%M:%S")
            
            # 임계값 계산
            threshold = config.CAMERA_OFF_THRESHOLD
            leave_threshold = config.LEAVE_ALERT_THRESHOLD
            
            camera_exceeded = sum(
                1 for s in camera_off 
                if (now_utc - self._ensure_utc(s.last_status_change)).total_seconds() / 60 >= threshold
            )
            leave_exceeded = sum(
                1 for s in left_students 
                if (now_utc - self._ensure_utc(s.last_leave_time)).total_seconds() / 60 >= leave_threshold
            )
            
            # 현재 접속 중인 수강생 수 계산
            currently_connected = len(camera_on) + len(camera_off)
            
            # 총 등록 학생 수 (관리자 제외)
            total_students = len(camera_on) + len(camera_off) + len(left_students) + len(not_connected)
            
            print("\n" + "=" * 60)
            print(f"📊 학생 상태 ({current_time})")
            print("=" * 60)
            print()
            
            # 모니터링 상태 표시
            today = date.today()
            checker = self.monitor_service.holiday_checker
            
            if self.monitor_service.is_monitoring_paused:
                print("   ⏸️  모니터링 상태       : 일시정지 (수동)")
                print()
            elif checker.is_weekend_or_holiday(today):
                reason = "주말" if checker.is_weekend(today) else "공휴일"
                print(f"   ⏸️  모니터링 상태       : 일시정지 ({reason})")
                print()
            
            # DM 발송 상태 표시
            if self.monitor_service.is_dm_paused:
                print("   🔕 DM 발송 상태         : ⏸️  일시정지 중")
                print()
            
            print(f"   🟢 카메라 ON            : {len(camera_on)}명")
            print(f"   🔴 카메라 OFF           : {len(camera_off)}명" + (f" (⚠️ 임계값 초과: {camera_exceeded}명)" if camera_exceeded > 0 else ""))
            print(f"   🚪 접속 종료            : {len(left_students)}명" + (f" (⚠️ 임계값 초과: {leave_exceeded}명)" if leave_exceeded > 0 else ""))
            print(f"   ⚪ 미접속 (휴가/병가)   : {len(not_connected)}명")
            print()
            print(f"   💻 현재 접속 중         : {currently_connected}명")
            print(f"   📊 총 등록 (관리자 제외): {total_students}명")
            print(f"   ⚠️  전체 임계값 초과    : {camera_exceeded + leave_exceeded}명")
            
            print("\n" + "=" * 60)
            print("💡 상세 정보:")
            print("   [o+Enter] - 카메라 OFF 학생 상세")
            print("   [l+Enter] - 접속 종료 학생 상세")
            print("   [n+Enter] - 미접속 학생 상세")
            print("   [q+Enter] - 종료  |  [h+Enter] - 도움말")
            print("=" * 60)
            print()
        
        except Exception as e:
            print(f"\n❌ 상태 조회 실패: {e}")
    
    async def _print_off_students(self):
        """OFF 상태인 학생들만 출력 (나간 시각, 경과 시간)"""
        try:
            # 최신 데이터 조회
            all_students = await DBService.get_all_students()
            
            if not all_students:
                print("\n📊 등록된 학생이 없습니다.")
                return
            
            # 오늘 입장한 학생 목록 가져오기
            joined_today = self.slack_listener.get_joined_students_today()
            
            # OFF 상태인 학생만 필터링
            # 조건: 카메라 OFF + 접속 종료 안 함 + 오늘 접속함 + 관리자 제외
            off_students = [
                s for s in all_students 
                if not s.is_cam_on 
                and s.last_leave_time is None  # 접속 종료한 학생 제외
                and s.id in joined_today  # 오늘 미접속 학생 제외
                and not (s.discord_id and self.discord_bot.is_admin(s.discord_id))  # 관리자 제외
            ]
            
            if not off_students:
                print("\n" + "=" * 60)
                print("🔴 카메라 OFF 학생: 0명")
                print("=" * 60)
                print("   (모든 학생이 카메라를 켜고 있습니다.)")
                print()
                return
            
            # 현재 시간 (UTC로 계산, 로컬로 표시)
            now_local = datetime.now()
            now_utc = datetime.now(timezone.utc)
            current_time = now_local.strftime("%Y-%m-%d %H:%M:%S")
            
            print("\n" + "=" * 60)
            print(f"🔴 카메라 OFF 학생 목록 ({current_time})")
            print("=" * 60)
            print()
            
            # 경과 시간 기준으로 정렬 (긴 순서대로)
            off_students.sort(
                key=lambda s: (now_utc - self._ensure_utc(s.last_status_change)).total_seconds(),
                reverse=True
            )
            
            threshold = config.CAMERA_OFF_THRESHOLD
            
            for student in off_students:
                # UTC 시간을 로컬 시간으로 변환하여 표시
                last_change_utc = self._ensure_utc(student.last_status_change)
                
                # UTC를 로컬 시간으로 변환
                try:
                    last_change_local = last_change_utc.astimezone()
                    off_time_str = last_change_local.strftime("%H:%M")
                except:
                    # 변환 실패 시 UTC 시간 그대로 표시
                    off_time_str = student.last_status_change.strftime("%H:%M")
                
                # 경과 시간 계산 (UTC 기준)
                elapsed_minutes = int((now_utc - last_change_utc).total_seconds() / 60)
                elapsed_hours = elapsed_minutes // 60
                elapsed_mins = elapsed_minutes % 60
                
                # 경과 시간 표시 형식
                if elapsed_hours > 0:
                    elapsed_str = f"{elapsed_hours}시간 {elapsed_mins}분"
                else:
                    elapsed_str = f"{elapsed_minutes}분"
                
                # 임계값 초과 여부
                status_icon = "⚠️" if elapsed_minutes >= threshold else "  "
                
                # 한 줄로 간결하게 표시
                print(f"   {status_icon} {student.zep_name} - OFF 후 {elapsed_str} ({off_time_str}부터)")
            
            # 요약
            exceeded_count = len([s for s in off_students 
                                 if (now_utc - self._ensure_utc(s.last_status_change)).total_seconds() / 60 >= threshold])
            
            print("\n" + "=" * 60)
            print(f"📊 총 {len(off_students)}명 | ⚠️ 임계값 초과: {exceeded_count}명")
            print("=" * 60)
            print()
        
        except Exception as e:
            print(f"\n❌ OFF 학생 조회 실패: {e}")
            import traceback
            traceback.print_exc()
    
    async def _print_left_students(self):
        """접속 종료한 학생들만 출력 (나간 시각, 경과 시간)"""
        try:
            # 최신 데이터 조회
            all_students = await DBService.get_all_students()
            
            if not all_students:
                print("\n📊 등록된 학생이 없습니다.")
                return
            
            # 접속 종료한 학생만 필터링 (last_leave_time이 있는 학생 + 관리자 제외)
            left_students = [
                s for s in all_students 
                if s.last_leave_time is not None
                and not (s.discord_id and self.discord_bot.is_admin(s.discord_id))  # 관리자 제외
            ]
            
            if not left_students:
                print("\n" + "=" * 60)
                print("🚪 접속 종료 학생: 0명")
                print("=" * 60)
                print("   (접속 종료한 학생이 없습니다.)")
                print()
                return
            
            # 현재 시간 (UTC로 계산, 로컬로 표시)
            now_local = datetime.now()
            now_utc = datetime.now(timezone.utc)
            current_time = now_local.strftime("%Y-%m-%d %H:%M:%S")
            
            print("\n" + "=" * 60)
            print(f"🚪 접속 종료 학생 목록 ({current_time})")
            print("=" * 60)
            print()
            
            # 경과 시간 기준으로 정렬 (긴 순서대로)
            left_students.sort(
                key=lambda s: (now_utc - self._ensure_utc(s.last_leave_time)).total_seconds() if s.last_leave_time else 0,
                reverse=True
            )
            
            threshold = config.LEAVE_ALERT_THRESHOLD
            
            for student in left_students:
                if not student.last_leave_time:
                    continue
                
                # UTC 시간을 로컬 시간으로 변환하여 표시
                leave_time_utc = self._ensure_utc(student.last_leave_time)
                
                # UTC를 로컬 시간으로 변환
                try:
                    leave_time_local = leave_time_utc.astimezone()
                    leave_time_str = leave_time_local.strftime("%H:%M")
                except:
                    # 변환 실패 시 UTC 시간 그대로 표시
                    leave_time_str = student.last_leave_time.strftime("%H:%M")
                
                # 경과 시간 계산 (UTC 기준)
                elapsed_minutes = int((now_utc - leave_time_utc).total_seconds() / 60)
                elapsed_hours = elapsed_minutes // 60
                elapsed_mins = elapsed_minutes % 60
                
                # 경과 시간 표시 형식
                if elapsed_hours > 0:
                    elapsed_str = f"{elapsed_hours}시간 {elapsed_mins}분"
                else:
                    elapsed_str = f"{elapsed_minutes}분"
                
                # 임계값 초과 여부
                status_icon = "⚠️" if elapsed_minutes >= threshold else "  "
                
                # 외출/조퇴 상태 표시
                status_text = ""
                if student.is_absent:
                    if student.absent_type == "leave":
                        status_text = " [외출]"
                    elif student.absent_type == "early_leave":
                        status_text = " [조퇴]"
                
                # 한 줄로 간결하게 표시
                print(f"   {status_icon} {student.zep_name}{status_text} - 종료 후 {elapsed_str} ({leave_time_str}부터)")
            
            # 요약
            exceeded_count = len([s for s in left_students 
                                 if s.last_leave_time and 
                                 (now_utc - self._ensure_utc(s.last_leave_time)).total_seconds() / 60 >= threshold])
            absent_count = len([s for s in left_students if s.is_absent])
            
            print("\n" + "=" * 60)
            print(f"📊 총 {len(left_students)}명 | ⚠️ 임계값 초과: {exceeded_count}명 | 외출/조퇴: {absent_count}명")
            print("=" * 60)
            print()
        
        except Exception as e:
            print(f"\n❌ 접속 종료 학생 조회 실패: {e}")
            import traceback
            traceback.print_exc()
    
    async def _print_not_joined_students(self):
        """오늘 접속하지 않은 학생들만 출력"""
        try:
            # 최신 데이터 조회
            all_students = await DBService.get_all_students()
            
            if not all_students:
                print("\n📊 등록된 학생이 없습니다.")
                return
            
            # 오늘 입장한 학생 목록 가져오기
            joined_today = self.slack_listener.get_joined_students_today()
            
            # 접속하지 않은 학생 필터링 (관리자 제외)
            not_joined_students = [
                student for student in all_students
                if student.id not in joined_today 
                and student.last_leave_time is None
                and not (student.discord_id and self.discord_bot.is_admin(student.discord_id))  # 관리자 제외
            ]
            
            # 현재 시간
            now_local = datetime.now()
            current_time = now_local.strftime("%Y-%m-%d %H:%M:%S")
            
            if not not_joined_students:
                print("\n" + "=" * 60)
                print(f"✅ 오늘 미접속 학생 목록 ({current_time})")
                print("=" * 60)
                print("   (모든 학생이 오늘 접속했습니다.)")
                print()
                return
            
            print("\n" + "=" * 60)
            print(f"⚪ 오늘 미접속 학생 목록 ({current_time})")
            print("=" * 60)
            print(f"총 {len(not_joined_students)}명")
            print()
            
            # 이름순 정렬
            not_joined_students.sort(key=lambda s: s.zep_name)
            
            for student in not_joined_students:
                # Discord 등록 여부 표시
                discord_status = "[Discord 미등록]" if not student.discord_id else ""
                print(f"   • {student.zep_name} {discord_status}")
            
            print("\n" + "=" * 60)
            print(f"📊 총 {len(not_joined_students)}명 (전체 {len(all_students)}명 중 {len(not_joined_students)/len(all_students)*100:.1f}%)")
            print("=" * 60)
            print()
        
        except Exception as e:
            print(f"\n❌ 접속하지 않은 학생 조회 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def _print_help(self):
        """도움말 출력"""
        print("\n" + "=" * 60)
        print("⌨️  터미널 단축키 도움말")
        print("=" * 60)
        print("\n📊 상태 확인:")
        print("  [Enter] 또는 [s+Enter]        - 전체 학생 상태 요약")
        print("\n📋 상세 목록:")
        print("  [o+Enter] 또는 [off+Enter]    - 카메라 OFF 학생 상세 (경과 시간 포함)")
        print("  [l+Enter] 또는 [leave+Enter]  - 접속 종료 학생 상세 (경과 시간 포함)")
        print("  [n+Enter] 또는 [not_joined]   - 오늘 미접속 학생 상세 (휴가/병가)")
        print("\n🔔 DM 제어:")
        print("  [p+Enter] 또는 [pause+Enter]  - 전체 DM 발송 일시정지")
        print("  [r+Enter] 또는 [resume+Enter] - 전체 DM 발송 재개")
        print("\n🎛️  시스템:")
        print("  [q+Enter] 또는 [quit+Enter]   - 프로그램 종료")
        print("  [h+Enter] 또는 [help+Enter]   - 이 도움말 표시")
        print("\n" + "=" * 60)
        print("💡 Tip: Enter만 입력하면 전체 요약을 빠르게 확인할 수 있습니다.")
        print("=" * 60)
        print()


async def main():
    """메인 실행 함수"""
    # 시스템 인스턴스 생성
    system = ZepMonitoringSystem()
    
    # Graceful Shutdown 핸들러
    def signal_handler(sig, frame):
        print("\n⚠️ 종료 신호 수신")
        # 플래그만 설정하고 정상 종료 프로세스 시작
        system.is_running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 시스템 초기화 및 시작
        await system.initialize()
        await system.start()
    except KeyboardInterrupt:
        print("\n⚠️ 사용자 중단")
    except Exception as e:
        print(f"\n❌ 치명적 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 정상적으로 종료 처리
        await system.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 프로그램 종료")
    except Exception as e:
        print(f"\n❌ 프로그램 오류: {e}")
        sys.exit(1)

