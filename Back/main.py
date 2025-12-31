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
        self.is_shutting_down = False
        self.ws_manager = manager
    
    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        """
        datetime을 UTC timezone-aware로 올바르게 변환

        Args:
            dt: datetime 객체 (aware 또는 naive)

        Returns:
            UTC timezone-aware datetime
        """
        from database.db_service import to_utc
        if dt.tzinfo is None:
            # naive datetime은 서울 시간으로 가정 후 UTC 변환
            return to_utc(dt)
        return dt
    
    async def initialize(self):
        """모든 서비스 초기화"""
        print("=" * 60)
        print("🚀 ZEP Student Monitoring System (Slack Socket Mode)")
        print("=" * 60)
        
        print("📊 데이터베이스 초기화 중...")
        try:
            await init_db()
            await admin_manager.refresh()
            print("✅ 데이터베이스 초기화 완료")
        except Exception as e:
            print(f"❌ 데이터베이스 초기화 실패: {e}")
            raise

        # CSV 파일로 학생 일괄 등록 (있으면)
        try:
            from utils.csv_loader import load_students_from_csv
            added, skipped, errors = await load_students_from_csv("students.csv")

            if added > 0 or skipped > 0:
                print(f"📋 CSV 학생 등록: 신규 {added}명, 기존 {skipped}명 스킵")
                if errors:
                    print(f"⚠️ CSV 등록 경고: {len(errors)}건")
                    for error in errors[:5]:  # 최대 5개만 출력
                        print(f"   - {error}")
        except Exception as e:
            # CSV 파일 없거나 오류 발생해도 계속 진행
            pass

        print("🤖 Discord Bot 초기화 중...")
        try:
            self.discord_bot = DiscordBot()
            print("✅ Discord Bot 생성 완료")
        except Exception as e:
            print(f"❌ Discord Bot 초기화 실패: {e}")
            raise
        
        print("👀 Monitor Service 초기화 중...")
        try:
            self.monitor_service = MonitorService(self.discord_bot)
            self.discord_bot.set_monitor_service(self.monitor_service)
            print("✅ Monitor Service 생성 완료")
        except Exception as e:
            print(f"❌ Monitor Service 초기화 실패: {e}")
            raise
        
        print("💬 Slack Listener 초기화 중...")
        try:
            self.slack_listener = SlackListener(self.monitor_service)
            self.monitor_service.set_slack_listener(self.slack_listener)
            print("✅ Slack Listener 생성 완료")
        except Exception as e:
            print(f"❌ Slack Listener 초기화 실패: {e}")
            raise
        
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
        global _system_instance
        
        print("\n🚀 시스템 시작 중...\n")
        
        try:
            discord_task = asyncio.create_task(
                self.discord_bot.start(config.DISCORD_BOT_TOKEN)
            )
            self.tasks.append(discord_task)
            
            print("⏳ Discord Bot 연결 중...")
            await asyncio.sleep(3)
            await self.discord_bot.wait_until_ready()
            print(f"✅ Discord Bot 준비 완료: {self.discord_bot.user.name}#{self.discord_bot.user.discriminator}")
            
            await self._print_admin_info()

            # ⭐ 일일 초기화를 먼저 실행 (Slack 동기화 전에)
            # 초기화 후 Slack 동기화를 통해 최신 상태를 반영
            print("\n🔧 프로그램 시작 시 초기화 확인 중...")
            await self.monitor_service._check_startup_reset()

            # ⭐ Slack 동기화를 백그라운드로 실행 (API 서버 시작을 막지 않음)
            async def run_slack_sync():
                # 오늘 초기화 시간(서울 07:00 -> UTC 변환됨)부터 현재까지의 시간 계산
                # monitor_service.reset_time은 이미 서울 07:00을 UTC로 변환한 값
                if self.monitor_service.reset_time:
                    reset_time_utc = self.monitor_service.reset_time
                    now_utc = datetime.now(timezone.utc)
                    hours_since_reset = (now_utc - reset_time_utc).total_seconds() / 3600
                    lookback_hours = max(1, int(hours_since_reset) + 1)  # 최소 1시간, 여유있게 +1시간
                else:
                    lookback_hours = 24  # fallback

                print(f"\n📡 Slack 히스토리 동기화 시작 (최근 {lookback_hours}시간)...")
                print(f"[디버그] restore_state_from_history() 호출 직전")
                await self.slack_listener.restore_state_from_history(lookback_hours=lookback_hours)
                print(f"[디버그] restore_state_from_history() 호출 완료")
                print("✅ Slack 동기화 완료\n")
                # 동기화 완료 후 실시간 리스닝 시작
                slack_task = asyncio.create_task(self.slack_listener.start_listener())
                self.tasks.append(slack_task)
                await asyncio.sleep(1)
                print("✅ Slack 실시간 리스닝 시작됨")

            # 백그라운드에서 Slack 동기화 실행
            asyncio.create_task(run_slack_sync())

            # ⭐ Monitor Service 시작 (_check_startup_reset은 이미 실행했으므로 제외)
            monitor_task = asyncio.create_task(self.monitor_service.start_without_reset())
            self.tasks.append(monitor_task)

            # ⭐ Google Sheets 자동 동기화 시작 (1시간 간격)
            google_sync_task = asyncio.create_task(self._run_google_sheets_sync())
            self.tasks.append(google_sync_task)
            
            if self.screen_monitor:
                screen_task = asyncio.create_task(self.screen_monitor.start())
                self.tasks.append(screen_task)
            
            if _system_instance is None:
                _system_instance = self
            
            from api.server import app
            app.state.system_instance = self

            # Uvicorn 로깅 필터 설정 (health check 로그 제한)
            import logging
            from datetime import datetime, timedelta

            class HealthCheckFilter(logging.Filter):
                """헬스 체크 로그를 1시간에 1회만 출력하는 필터"""
                def __init__(self):
                    super().__init__()
                    self.last_log_time = None

                def filter(self, record):
                    # /health 엔드포인트가 아니면 모두 허용
                    if not hasattr(record, 'args') or not record.args:
                        return True

                    # 로그 메시지에서 /health 체크
                    msg = str(record.getMessage())
                    if 'GET /health' not in msg:
                        return True

                    # /health 엔드포인트는 1시간에 1회만 로그
                    now = datetime.now()
                    if self.last_log_time is None or (now - self.last_log_time) >= timedelta(hours=1):
                        self.last_log_time = now
                        return True

                    return False

            # Uvicorn access 로거에 필터 추가
            uvicorn_logger = logging.getLogger("uvicorn.access")
            uvicorn_logger.addFilter(HealthCheckFilter())

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
            
            await asyncio.sleep(1)
            
            self._print_status()
            
            input_task = asyncio.create_task(self._handle_keyboard_input())
            self.tasks.append(input_task)
            
            try:
                while self.is_running:
                    await asyncio.sleep(1)
                    for task in self.tasks:
                        if task.done():
                            try:
                                await task
                            except Exception:
                                pass
            except Exception as e:
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
        if self.is_shutting_down:
            return
        
        if not self.is_running:
            return
        
        self.is_shutting_down = True
        
        print("\n" + "=" * 60)
        print("🛑 시스템 종료 중...")
        print("=" * 60)
        
        self.is_running = False
        
        if self.screen_monitor:
            try:
                await self.screen_monitor.stop()
            except Exception:
                pass
        
        if self.monitor_service:
            try:
                await self.monitor_service.stop()
            except Exception:
                pass
        
        if self.slack_listener:
            try:
                await self.slack_listener.stop()
            except Exception:
                pass
        
        if self.discord_bot:
            try:
                await self.discord_bot.close()
                print("🤖 Discord Bot 종료")
            except Exception:
                pass
        
        cancelled_tasks = []
        for task in self.tasks:
            if not task.done():
                task.cancel()
                cancelled_tasks.append(task)
        
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
        
        dm_status = "⏸️  일시정지" if self.monitor_service.is_dm_paused else "🔔 정상"
        print(f"  • DM 발송: {dm_status}")
        
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

    async def _broadcast_google_sync_notifications(self, result: dict) -> None:
        details = result.get("updated_details", [])
        seen_keys: set[str] = set()
        for detail in details:
            key_parts = [
                str(detail.get("student_id") or ""),
                str(detail.get("status") or ""),
                str(detail.get("start_date") or ""),
                str(detail.get("end_date") or ""),
                str(detail.get("time") or ""),
                str(detail.get("reason") or ""),
                str(detail.get("is_immediate") or ""),
            ]
            key = "|".join(key_parts)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            payload = {
                "student_id": detail.get("student_id") or 0,
                "student_name": detail.get("name") or "학생",
                "camp": detail.get("camp") or (config.CAMP_NAME or "캠프"),
                "status_type": detail.get("status") or "상태",
                "reason": detail.get("reason"),
                "start_date": detail.get("start_date"),
                "end_date": detail.get("end_date"),
                "time": detail.get("time"),
                "is_future_date": detail.get("is_future_date", False),
                "is_immediate": detail.get("is_immediate", False),
            }
            await self.ws_manager.broadcast_status_notification(payload)

    async def _run_google_sheets_sync(self):
        """Google Sheets 자동 동기화 (1시간 간격)"""
        from services.google_sheets_service import google_sheets_service

        interval_seconds = 60 * 60
        await asyncio.sleep(5)

        while self.is_running:
            if config.GOOGLE_SHEETS_URL:
                try:
                    result = await google_sheets_service.sync_status_from_sheets()
                    if result.get("success"):
                        details = result.get("updated_details", []) or []
                        if details:
                            await self._broadcast_google_sync_notifications(result)
                            if self.monitor_service:
                                await self.monitor_service.broadcast_dashboard_update_now()
                    else:
                        error = result.get("error", "알 수 없는 오류")
                        print(f"⚠️ 구글 시트 자동 동기화 실패: {error}")
                except Exception as e:
                    print(f"⚠️ 구글 시트 자동 동기화 실패: {e}")

            await asyncio.sleep(interval_seconds)
    
    async def _handle_keyboard_input(self):
        """키보드 입력 핸들러 (터미널 단축키)"""
        import threading
        import queue
        
        command_queue = queue.Queue()
        
        def input_thread():
            while self.is_running:
                try:
                    line = input()
                    if line.strip() and self.is_running:
                        command_queue.put(line.strip())
                except (EOFError, KeyboardInterrupt):
                    break
                except Exception:
                    pass
        
        thread = threading.Thread(target=input_thread, daemon=True)
        thread.start()
        
        while self.is_running:
            try:
                try:
                    command = command_queue.get_nowait()
                    await self._process_command(command)
                except queue.Empty:
                    pass
                
                await asyncio.sleep(0.1)
            except Exception:
                await asyncio.sleep(1)
    
    async def _process_command(self, command: str):
        """명령어 처리"""
        command = command.lower().strip()
        
        if command == 'q' or command == 'quit':
            print("\n⚠️ 종료 요청 수신")
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
            
            joined_today = self.slack_listener.get_joined_students_today()
            
            camera_on = []
            camera_off = []
            left_students = []
            not_connected = []
            
            for student in all_students:
                if student.discord_id and self.discord_bot.is_admin(student.discord_id):
                    continue
                
                if student.last_leave_time:
                    left_students.append(student)
                elif student.is_cam_on:
                    camera_on.append(student)
                else:
                    if student.id in joined_today:
                        camera_off.append(student)
                    else:
                        not_connected.append(student)
            
            now_local = datetime.now()
            now_utc = datetime.now(timezone.utc)
            current_time = now_local.strftime("%Y-%m-%d %H:%M:%S")
            
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
            
            currently_connected = len(camera_on) + len(camera_off)
            total_students = len(camera_on) + len(camera_off) + len(left_students) + len(not_connected)
            
            print("\n" + "=" * 60)
            print(f"📊 학생 상태 ({current_time})")
            print("=" * 60)
            print()
            
            today = date.today()
            checker = self.monitor_service.holiday_checker
            
            if self.monitor_service.is_monitoring_paused:
                print("   ⏸️  모니터링 상태       : 일시정지 (수동)")
                print()
            elif checker.is_weekend_or_holiday(today):
                reason = "주말" if checker.is_weekend(today) else "공휴일"
                print(f"   ⏸️  모니터링 상태       : 일시정지 ({reason})")
                print()
            
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
            all_students = await DBService.get_all_students()
            
            if not all_students:
                print("\n📊 등록된 학생이 없습니다.")
                return
            
            joined_today = self.slack_listener.get_joined_students_today()
            
            off_students = [
                s for s in all_students 
                if not s.is_cam_on 
                and s.last_leave_time is None
                and s.id in joined_today
                and not (s.discord_id and self.discord_bot.is_admin(s.discord_id))
            ]
            
            if not off_students:
                print("\n" + "=" * 60)
                print("🔴 카메라 OFF 학생: 0명")
                print("=" * 60)
                print("   (모든 학생이 카메라를 켜고 있습니다.)")
                print()
                return
            
            now_local = datetime.now()
            now_utc = datetime.now(timezone.utc)
            current_time = now_local.strftime("%Y-%m-%d %H:%M:%S")
            
            print("\n" + "=" * 60)
            print(f"🔴 카메라 OFF 학생 목록 ({current_time})")
            print("=" * 60)
            print()
            
            off_students.sort(
                key=lambda s: (now_utc - self._ensure_utc(s.last_status_change)).total_seconds(),
                reverse=True
            )
            
            threshold = config.CAMERA_OFF_THRESHOLD
            
            for student in off_students:
                last_change_utc = self._ensure_utc(student.last_status_change)
                
                try:
                    last_change_local = last_change_utc.astimezone()
                    off_time_str = last_change_local.strftime("%H:%M")
                except:
                    off_time_str = student.last_status_change.strftime("%H:%M")
                
                elapsed_minutes = int((now_utc - last_change_utc).total_seconds() / 60)
                elapsed_hours = elapsed_minutes // 60
                elapsed_mins = elapsed_minutes % 60
                
                if elapsed_hours > 0:
                    elapsed_str = f"{elapsed_hours}시간 {elapsed_mins}분"
                else:
                    elapsed_str = f"{elapsed_minutes}분"
                
                status_icon = "⚠️" if elapsed_minutes >= threshold else "  "
                
                print(f"   {status_icon} {student.zep_name} - OFF 후 {elapsed_str} ({off_time_str}부터)")
            
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
            all_students = await DBService.get_all_students()
            
            if not all_students:
                print("\n📊 등록된 학생이 없습니다.")
                return
            
            left_students = [
                s for s in all_students 
                if s.last_leave_time is not None
                and not (s.discord_id and self.discord_bot.is_admin(s.discord_id))
            ]
            
            if not left_students:
                print("\n" + "=" * 60)
                print("🚪 접속 종료 학생: 0명")
                print("=" * 60)
                print("   (접속 종료한 학생이 없습니다.)")
                print()
                return
            
            now_local = datetime.now()
            now_utc = datetime.now(timezone.utc)
            current_time = now_local.strftime("%Y-%m-%d %H:%M:%S")
            
            print("\n" + "=" * 60)
            print(f"🚪 접속 종료 학생 목록 ({current_time})")
            print("=" * 60)
            print()
            
            left_students.sort(
                key=lambda s: (now_utc - self._ensure_utc(s.last_leave_time)).total_seconds() if s.last_leave_time else 0,
                reverse=True
            )
            
            threshold = config.LEAVE_ALERT_THRESHOLD
            
            for student in left_students:
                if not student.last_leave_time:
                    continue
                
                leave_time_utc = self._ensure_utc(student.last_leave_time)
                
                try:
                    leave_time_local = leave_time_utc.astimezone()
                    leave_time_str = leave_time_local.strftime("%H:%M")
                except:
                    leave_time_str = student.last_leave_time.strftime("%H:%M")
                
                elapsed_minutes = int((now_utc - leave_time_utc).total_seconds() / 60)
                elapsed_hours = elapsed_minutes // 60
                elapsed_mins = elapsed_minutes % 60
                
                if elapsed_hours > 0:
                    elapsed_str = f"{elapsed_hours}시간 {elapsed_mins}분"
                else:
                    elapsed_str = f"{elapsed_minutes}분"
                
                status_icon = "⚠️" if elapsed_minutes >= threshold else "  "
                
                status_text = ""
                if student.is_absent:
                    if student.absent_type == "leave":
                        status_text = " [외출]"
                    elif student.absent_type == "early_leave":
                        status_text = " [조퇴]"
                
                print(f"   {status_icon} {student.zep_name}{status_text} - 종료 후 {elapsed_str} ({leave_time_str}부터)")
            
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
        """오늘 초기화 시간 이후 접속하지 않은 학생들만 출력"""
        try:
            all_students = await DBService.get_all_students()
            
            if not all_students:
                print("\n📊 등록된 학생이 없습니다.")
                return
            
            joined_today = self.slack_listener.get_joined_students_today()
            
            not_joined_students = [
                student for student in all_students
                if student.id not in joined_today  # 오늘 초기화 시간 이후 입장하지 않음
                and student.last_leave_time is None  # 퇴장하지 않음
                and not (student.discord_id and self.discord_bot.is_admin(student.discord_id))
            ]
            
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
            
            not_joined_students.sort(key=lambda s: s.zep_name)
            
            for student in not_joined_students:
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
    system = ZepMonitoringSystem()
    
    def signal_handler(sig, frame):
        print("\n⚠️ 종료 신호 수신")
        system.is_running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await system.initialize()
        await system.start()
    except KeyboardInterrupt:
        print("\n⚠️ 사용자 중단")
    except Exception as e:
        print(f"\n❌ 치명적 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await system.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 프로그램 종료")
    except Exception as e:
        print(f"\n❌ 프로그램 오류: {e}")
        sys.exit(1)
