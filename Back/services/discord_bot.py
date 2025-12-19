"""
Discord Bot 서비스
학생 등록, DM 전송, 버튼 인터랙션 처리
"""
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone, date

from config import config
from database import DBService
from services.admin_manager import admin_manager
import re
import asyncio


class DiscordBot(commands.Bot):
    """Discord Bot 클래스"""
    
    def __init__(self):
        """Discord Bot 초기화"""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        
        self.db_service = DBService()
        self.is_ready = False
        self.monitor_service = None  # MonitorService 참조 (나중에 설정)
        
        # 이벤트 및 명령어 등록
        self._setup_events()
        self._setup_commands()
    
    def set_monitor_service(self, monitor_service):
        """MonitorService 참조 설정 (순환 참조 방지)"""
        self.monitor_service = monitor_service
    
    def is_admin(self, user_id: int) -> bool:
        """
        사용자가 관리자인지 확인
        
        Args:
            user_id: Discord 유저 ID
            
        Returns:
            관리자 여부
        """
        return admin_manager.is_admin(user_id)
    
    def _extract_name_only(self, zep_name: str) -> str:
        """
        ZEP 이름에서 실제 이름만 추출 (SlackListener와 동일한 로직)

        Args:
            zep_name: ZEP 이름

        Returns:
            한글이 포함된 이름 부분만 반환
        """
        if not zep_name:
            return ""

        # 먼저 * 제거 (Slack 강조 표시)
        zep_name = zep_name.strip('*').strip()

        # 구분자 확대: /_-|공백 + .()@{}[]*
        parts = re.split(r'[/_\-|\s.()@{}\[\]\*]+', zep_name.strip())
        parts = [part.strip() for part in parts if part.strip()]

        korean_parts = []
        for part in parts:
            if any('\uAC00' <= char <= '\uD7A3' for char in part):
                # 한글이 포함된 part에서 숫자 제거
                korean_only = ''.join(c for c in part if '\uAC00' <= c <= '\uD7A3')
                if korean_only:
                    korean_parts.append(korean_only)

        # 역할 키워드 목록 (SlackListener와 동일)
        role_keywords = {
            "조교", "주강사", "멘토", "매니저", "코치",
            "개발자", "학생", "수강생", "교육생",
            "강사", "관리자", "운영자", "팀장", "회장",
            "강의", "실습", "프로젝트", "팀"
        }

        filtered = [part for part in korean_parts if part not in role_keywords]

        if filtered:
            return filtered[-1]
        elif korean_parts:
            return korean_parts[-1]

        return zep_name.strip()

    def _is_student_pattern(self, name: str) -> bool:
        """
        학생 이름 패턴 감지: 영어 + 숫자 + 한글 조합 (순서 무관)
        예: IH_02_배현우, 배현우_IH02, 02IH배현우 등

        Args:
            name: Discord 표시 이름

        Returns:
            bool: 학생 패턴 여부
        """
        has_english = bool(re.search(r'[A-Za-z]', name))
        has_digit = bool(re.search(r'\d', name))
        has_korean = bool(re.search(r'[\uAC00-\uD7A3]', name))

        # 세 가지가 모두 포함된 경우만 학생으로 판단
        return has_english and has_digit and has_korean

    async def get_guild_members(self):
        """
        Discord 서버의 모든 멤버 가져오기 + 학생 패턴 자동 감지

        Returns:
            List[Dict]: 멤버 정보 리스트
            [
                {
                    "discord_id": int,
                    "discord_name": str,
                    "display_name": str,
                    "is_student": bool  # 패턴 분석 결과
                },
                ...
            ]
        """
        if not config.DISCORD_SERVER_ID:
            raise ValueError("DISCORD_SERVER_ID가 설정되지 않았습니다. .env 파일에서 Discord 서버 ID를 설정해주세요.")

        try:
            guild_id = int(config.DISCORD_SERVER_ID)
            guild = self.get_guild(guild_id)

            if not guild:
                raise ValueError(f"Discord 서버 ID {guild_id}를 찾을 수 없습니다. 봇이 해당 서버에 초대되어 있는지 확인해주세요.")

            members = []

            # 비동기로 모든 멤버 가져오기
            async for member in guild.fetch_members(limit=None):
                # 봇 제외
                if member.bot:
                    continue

                display_name = member.display_name or member.name

                # 패턴 분석: 영어+숫자+한글 조합 감지
                is_student = self._is_student_pattern(display_name)

                # JSON 직렬화 시 JS 숫자 정밀도 손실을 막기 위해 문자열로 반환
                members.append({
                    "discord_id": str(member.id),
                    "discord_name": member.name,
                    "display_name": display_name,
                    "is_student": is_student
                })

            # 학생 패턴이 감지된 멤버를 앞에 정렬
            members.sort(key=lambda m: (not m["is_student"], m["display_name"]))

            return members

        except ValueError:
            raise
        except Exception as e:
            print(f"❌ [Discord] 멤버 가져오기 실패: {type(e).__name__}: {str(e)}")
            raise

    def _setup_events(self):
        """이벤트 핸들러 설정"""
        
        @self.event
        async def on_ready():
            """봇 준비 완료"""
            await admin_manager.ensure_loaded()
            self.is_ready = True
        
        @self.event
        async def on_interaction(interaction: discord.Interaction):
            """버튼 인터랙션 처리"""
            if interaction.type == discord.InteractionType.component:
                custom_id = interaction.data.get("custom_id")
                
                if custom_id == "absent":
                    await self._handle_button_response(interaction, custom_id)
                elif custom_id == "camera_on":
                    await self._handle_camera_check(interaction)
                elif custom_id.startswith("admin_leave_") or custom_id.startswith("admin_early_leave_"):
                    await self._handle_admin_absent_response(interaction, custom_id)
                elif custom_id.startswith("student_leave_") or custom_id.startswith("student_early_leave_"):
                    await self._handle_student_absent_response(interaction, custom_id)
                elif custom_id.startswith("admin_check_student_"):
                    await self._handle_admin_check_student(interaction, custom_id)
                elif custom_id.startswith("student_return_"):
                    await self._handle_student_return(interaction, custom_id)
    
    def _setup_commands(self):
        """명령어 설정"""
        
        @self.command(name="register")
        async def register(ctx, zep_name: str):
            """
            학생 등록 명령어
            사용법: !register 홍길동
            
            Args:
                zep_name: ZEP에서 사용하는 이름
            """
            discord_id = ctx.author.id
            
            try:
                existing = await self.db_service.get_student_by_discord_id(discord_id)
                if existing:
                    await ctx.send(f"❌ 이미 `{existing.zep_name}`으로 등록되어 있습니다.")
                    return
                
                extracted_name = self._extract_name_only(zep_name)
                
                existing_zep = await self.db_service.get_student_by_zep_name(extracted_name)
                if existing_zep:
                    await ctx.send(f"❌ `{extracted_name}`은(는) 이미 다른 사용자가 등록한 이름입니다.")
                    return
                
                # 학생 등록 (추출된 이름으로 저장)
                student = await self.db_service.add_student(extracted_name, discord_id)
                
                # 등록 완료 메시지
                await ctx.send(
                    f"✅ **등록 완료!**\n"
                    f"ZEP 이름: `{zep_name}`\n"
                    f"Discord: {ctx.author.mention}\n\n"
                    f"이제 카메라 모니터링이 활성화됩니다. 📷"
                )
                
                # DM으로도 안내
                try:
                    await ctx.author.send(
                        f"🎓 **ZEP 모니터링 시스템 등록 완료**\n\n"
                        f"등록 정보:\n"
                        f"• ZEP 이름: `{zep_name}`\n"
                        f"• Discord ID: {ctx.author.id}\n\n"
                        f"💡 카메라가 20분 이상 꺼져있으면 자동으로 알림을 받게 됩니다."
                    )
                except discord.Forbidden:
                    await ctx.send("⚠️ DM을 보낼 수 없습니다. DM 설정을 확인해주세요.")
                
                
            except Exception as e:
                await ctx.send(f"❌ 등록 중 오류가 발생했습니다: {str(e)}")
        
        @self.command(name="status")
        async def status(ctx):
            """
            본인의 현재 상태 확인
            사용법: !status
            """
            discord_id = ctx.author.id
            
            try:
                student = await self.db_service.get_student_by_discord_id(discord_id)
                
                if not student:
                    await ctx.send("❌ 등록되지 않은 사용자입니다. `!register [ZEP이름]`으로 등록해주세요.")
                    return
                
                cam_status = "🟢 ON" if student.is_cam_on else "🔴 OFF"
                last_change = student.last_status_change.strftime("%Y-%m-%d %H:%M:%S")
                
                embed = discord.Embed(
                    title="📊 내 상태",
                    color=discord.Color.blue()
                )
                embed.add_field(name="ZEP 이름", value=student.zep_name, inline=True)
                embed.add_field(name="카메라 상태", value=cam_status, inline=True)
                embed.add_field(name="마지막 변경", value=last_change, inline=False)
                embed.add_field(name="알림 받은 횟수", value=f"{student.alert_count}회", inline=True)
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                await ctx.send(f"❌ 상태 조회 중 오류가 발생했습니다.")
        
        @self.command(name="admin_register")
        async def admin_register(ctx, zep_name: str, user: discord.User):
            """
            관리자 전용 - 다른 사용자 등록
            사용법: !admin_register 홍길동 @유저
            
            Args:
                zep_name: ZEP에서 사용하는 이름
                user: 등록할 Discord 유저
            """
            # 관리자 권한 체크
            if not self.is_admin(ctx.author.id):
                await ctx.send("❌ 이 명령어는 관리자만 사용할 수 있습니다.")
                return
            
            try:
                discord_id = user.id
                
                # 이미 등록된 학생인지 확인
                existing = await self.db_service.get_student_by_discord_id(discord_id)
                if existing:
                    await ctx.send(f"❌ {user.mention}님은 이미 `{existing.zep_name}`으로 등록되어 있습니다.")
                    return
                
                # 이름 추출 (Slack 메시지와 동일한 로직)
                extracted_name = self._extract_name_only(zep_name)
                
                # ZEP 이름 중복 확인 (추출된 이름으로)
                existing_zep = await self.db_service.get_student_by_zep_name(extracted_name)
                if existing_zep:
                    await ctx.send(f"❌ `{extracted_name}`은(는) 이미 등록되어 있습니다.")
                    return
                
                # 학생 등록 (추출된 이름으로 저장)
                student = await self.db_service.add_student(extracted_name, discord_id)
                
                # 등록 완료 메시지
                await ctx.send(
                    f"✅ **관리자 등록 완료!**\n"
                    f"ZEP 이름: `{extracted_name}`\n"
                    f"Discord: {user.mention}\n"
                    f"등록자: {ctx.author.mention}"
                )
                
                try:
                    await user.send(
                        f"🎓 **ZEP 모니터링 시스템 등록 완료**\n\n"
                        f"관리자({ctx.author})님이 등록하셨습니다.\n\n"
                        f"등록 정보:\n"
                        f"• ZEP 이름: `{extracted_name}`\n"
                        f"• Discord ID: {user.id}\n\n"
                        f"💡 카메라가 20분 이상 꺼져있으면 자동으로 알림을 받게 됩니다."
                    )
                except discord.Forbidden:
                    await ctx.send(f"⚠️ {user.mention}님에게 DM을 보낼 수 없습니다.")
                
            except Exception as e:
                await ctx.send(f"❌ 등록 중 오류가 발생했습니다: {e}")
        
        @self.command(name="list_students")
        async def list_students(ctx):
            """관리자 전용 - 등록된 학생 목록 조회"""
            # 관리자 권한 체크
            if not self.is_admin(ctx.author.id):
                await ctx.send("❌ 이 명령어는 관리자만 사용할 수 있습니다.")
                return
            
            try:
                students = await self.db_service.get_all_students()
                
                if not students:
                    await ctx.send("등록된 학생이 없습니다.")
                    return
                
                embed = discord.Embed(
                    title="📋 등록된 학생 목록",
                    description=f"총 {len(students)}명",
                    color=discord.Color.blue()
                )
                
                # 10명씩 나눠서 표시
                for i in range(0, len(students), 10):
                    batch = students[i:i+10]
                    field_value = ""
                    
                    for student in batch:
                        status = "📷 ON" if student.is_cam_on else "📷 OFF"
                        field_value += f"• `{student.zep_name}` - <@{student.discord_id}> {status}\n"
                    
                    embed.add_field(
                        name=f"학생 {i+1}~{min(i+10, len(students))}",
                        value=field_value,
                        inline=False
                    )
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                await ctx.send(f"❌ 목록 조회 중 오류가 발생했습니다.")
        
        @self.command(name="help")
        async def help_command(ctx):
            """도움말 표시"""
            is_admin = self.is_admin(ctx.author.id)
            
            embed = discord.Embed(
                title="🎓 ZEP 모니터링 시스템 도움말",
                description="카메라 상태를 자동으로 모니터링하는 시스템입니다.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📝 !register [ZEP이름]",
                value="시스템에 등록합니다.\n예: `!register 홍길동`",
                inline=False
            )
            
            embed.add_field(
                name="📊 !status",
                value="현재 상태를 확인합니다.",
                inline=False
            )
            
            if is_admin:
                embed.add_field(
                    name="👨‍💼 관리자 명령어",
                    value=(
                        "• `!admin_register [ZEP이름] @유저` - 다른 사용자 등록\n"
                        "• `!list_students` - 등록된 학생 목록 조회"
                    ),
                    inline=False
                )
            
            embed.add_field(
                name="❓ !help",
                value="이 도움말을 표시합니다.",
                inline=False
            )
            
            if is_admin:
                embed.add_field(
                    name="🎛️ 모니터링 제어",
                    value=(
                        "• `!monitor-pause` - 모니터링 일시정지\n"
                        "• `!monitor-resume` - 모니터링 재개\n"
                        "• `!holiday-add [YYYY-MM-DD]` - 공휴일 추가\n"
                        "• `!holiday-remove [YYYY-MM-DD]` - 공휴일 제거\n"
                        "• `!holiday-list` - 공휴일 목록 조회"
                    ),
                    inline=False
                )
            
            embed.add_field(
                name="💡 작동 방식",
                value=(
                    "1. ZEP에서 카메라를 끄면 Slack으로 메시지 전송\n"
                    "2. 20분 경과 시 Discord DM으로 알림\n"
                    "3. 버튼으로 상황 응답\n"
                    "4. 강사 채널에 자동 알림"
                ),
                inline=False
            )
            
            await ctx.send(embed=embed)
        
        @self.command(name="monitor-pause")
        async def monitor_pause(ctx):
            """관리자 전용 - 모니터링 일시정지"""
            if not self.is_admin(ctx.author.id):
                await ctx.send("❌ 이 명령어는 관리자만 사용할 수 있습니다.")
                return
            
            if not self.monitor_service:
                await ctx.send("❌ 모니터링 서비스가 연결되지 않았습니다.")
                return
            
            self.monitor_service.pause_monitoring()
            await ctx.send("⏸️ **모니터링이 일시정지되었습니다.**\n주말/공휴일이 아니어도 모니터링이 중단됩니다.")
        
        @self.command(name="monitor-resume")
        async def monitor_resume(ctx):
            """관리자 전용 - 모니터링 재개"""
            if not self.is_admin(ctx.author.id):
                await ctx.send("❌ 이 명령어는 관리자만 사용할 수 있습니다.")
                return
            
            if not self.monitor_service:
                await ctx.send("❌ 모니터링 서비스가 연결되지 않았습니다.")
                return
            
            self.monitor_service.resume_monitoring()
            
            # 현재 상태 확인
            today = date.today()
            is_weekend = self.monitor_service.holiday_checker.is_weekend(today)
            is_holiday = self.monitor_service.holiday_checker.is_holiday(today)
            
            status_msg = "✅ **모니터링이 재개되었습니다.**"
            if is_weekend or is_holiday:
                reason = "주말" if is_weekend else "공휴일"
                status_msg += f"\n⚠️ 오늘은 {reason}이므로 자동으로 모니터링이 중단됩니다."
            
            await ctx.send(status_msg)
        
        @self.command(name="holiday-add")
        async def holiday_add(ctx, date_str: str):
            """관리자 전용 - 수동 공휴일 추가"""
            if not self.is_admin(ctx.author.id):
                await ctx.send("❌ 이 명령어는 관리자만 사용할 수 있습니다.")
                return
            
            if not self.monitor_service:
                await ctx.send("❌ 모니터링 서비스가 연결되지 않았습니다.")
                return
            
            try:
                # 날짜 파싱 (YYYY-MM-DD 형식)
                holiday_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                # 공휴일 추가
                success = self.monitor_service.holiday_checker.add_manual_holiday(holiday_date)
                
                if success:
                    await ctx.send(f"✅ **공휴일이 추가되었습니다.**\n날짜: {holiday_date.strftime('%Y년 %m월 %d일')} ({holiday_date.strftime('%A')})")
                else:
                    await ctx.send(f"⚠️ 해당 날짜는 이미 공휴일로 등록되어 있습니다.\n날짜: {holiday_date.strftime('%Y년 %m월 %d일')}")
                    
            except ValueError:
                await ctx.send("❌ 날짜 형식이 잘못되었습니다.\n사용법: `!holiday-add 2025-12-25`")
            except Exception as e:
                await ctx.send(f"❌ 공휴일 추가 중 오류가 발생했습니다: {e}")
        
        @self.command(name="holiday-remove")
        async def holiday_remove(ctx, date_str: str):
            """관리자 전용 - 수동 공휴일 제거"""
            if not self.is_admin(ctx.author.id):
                await ctx.send("❌ 이 명령어는 관리자만 사용할 수 있습니다.")
                return
            
            if not self.monitor_service:
                await ctx.send("❌ 모니터링 서비스가 연결되지 않았습니다.")
                return
            
            try:
                # 날짜 파싱 (YYYY-MM-DD 형식)
                holiday_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                # 공휴일 제거
                success = self.monitor_service.holiday_checker.remove_manual_holiday(holiday_date)
                
                if success:
                    await ctx.send(f"✅ **공휴일이 제거되었습니다.**\n날짜: {holiday_date.strftime('%Y년 %m월 %d일')}")
                else:
                    await ctx.send(f"⚠️ 해당 날짜는 공휴일로 등록되어 있지 않습니다.\n날짜: {holiday_date.strftime('%Y년 %m월 %d일')}")
                    
            except ValueError:
                await ctx.send("❌ 날짜 형식이 잘못되었습니다.\n사용법: `!holiday-remove 2025-12-25`")
            except Exception as e:
                await ctx.send(f"❌ 공휴일 제거 중 오류가 발생했습니다: {e}")
        
        @self.command(name="holiday-list")
        async def holiday_list(ctx):
            """관리자 전용 - 공휴일 목록 조회"""
            if not self.is_admin(ctx.author.id):
                await ctx.send("❌ 이 명령어는 관리자만 사용할 수 있습니다.")
                return
            
            if not self.monitor_service:
                await ctx.send("❌ 모니터링 서비스가 연결되지 않았습니다.")
                return
            
            try:
                today = date.today()
                checker = self.monitor_service.holiday_checker
                
                # 올해 모든 공휴일 가져오기
                all_holidays = checker.get_all_holidays(today.year)
                manual_holidays = checker.get_manual_holidays()
                
                # 오늘 상태
                is_weekend = checker.is_weekend(today)
                is_holiday = checker.is_holiday(today)
                
                embed = discord.Embed(
                    title="📅 공휴일 목록",
                    description=f"{today.year}년 공휴일 정보",
                    color=discord.Color.blue()
                )
                
                # 오늘 상태
                today_status = []
                if is_weekend:
                    today_status.append("주말")
                if is_holiday:
                    today_status.append("공휴일")
                
                if today_status:
                    embed.add_field(
                        name="📆 오늘",
                        value=f"{today.strftime('%Y년 %m월 %d일')} ({', '.join(today_status)})",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="📆 오늘",
                        value=f"{today.strftime('%Y년 %m월 %d일')} (평일)",
                        inline=False
                    )
                
                # 수동 추가 공휴일
                if manual_holidays:
                    manual_list = sorted([d for d in manual_holidays if d.year == today.year])
                    if manual_list:
                        manual_str = "\n".join([f"• {d.strftime('%Y-%m-%d')} ({d.strftime('%A')})" for d in manual_list])
                        embed.add_field(
                            name="✏️ 수동 추가 공휴일",
                            value=manual_str,
                            inline=False
                        )
                
                # 전체 공휴일 수
                embed.add_field(
                    name="📊 통계",
                    value=f"총 {len(all_holidays)}개 공휴일\n수동 추가: {len([d for d in manual_holidays if d.year == today.year])}개",
                    inline=False
                )
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                await ctx.send(f"❌ 공휴일 목록 조회 중 오류가 발생했습니다: {e}")
    
    async def send_camera_alert(self, student) -> bool:
        """
        학생에게 카메라 알림 DM 전송
        
        Args:
            student: Student 객체
            
        Returns:
            전송 성공 여부
        """
        try:
            if not student.last_status_change:
                return False

            user = await self.fetch_user(student.discord_id)

            # 경과 시간 계산
            last_change_utc = student.last_status_change if student.last_status_change.tzinfo else student.last_status_change.replace(tzinfo=timezone.utc)
            elapsed_minutes = int((datetime.now(timezone.utc) - last_change_utc).total_seconds() / 60)
            
            is_first_alert = (student.alert_count == 0)
            
            if is_first_alert:
                # 첫 알림: 버튼 포함
                embed = discord.Embed(
                    title="⚠️ 카메라 상태 알림",
                    description=f"{student.zep_name}님, 카메라가 꺼져 있습니다.",
                    color=discord.Color.orange()
                )
                
                embed.add_field(
                    name="📷 현재 상태",
                    value="카메라 OFF",
                    inline=True
                )
                
                embed.add_field(
                    name="⏱️ 경과 시간",
                    value=f"약 {elapsed_minutes}분",
                    inline=True
                )
                
                embed.add_field(
                    name="💡 안내",
                    value="현재 상황을 아래 버튼으로 알려주세요.\n카메라를 켜시면 알림이 중단됩니다.",
                    inline=False
                )
                
                # 인터랙티브 버튼 생성
                view = AlertView()
                await user.send(embed=embed, view=view)
                
            else:
                # 재알림: 버튼 없이 단순 메시지만
                await user.send(
                    f"⚠️ **{student.zep_name}님, 카메라가 여전히 꺼져 있습니다.**\n\n"
                    f"📷 현재 상태: 카메라 OFF\n"
                    f"⏱️ 경과 시간: 약 {elapsed_minutes}분\n\n"
                    f"💡 카메라를 켜주세요."
                )

            return True

        except discord.Forbidden:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - 사용자가 DM을 차단했거나 Discord 봇과 서버를 공유하지 않습니다"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
        except discord.NotFound:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - Discord 사용자를 찾을 수 없습니다"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
        except Exception as e:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - {type(e).__name__}: {str(e)}"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
    
    async def _handle_button_response(self, interaction: discord.Interaction, action: str):
        """
        버튼 응답 처리
        
        Args:
            interaction: Discord Interaction 객체
            action: 응답 유형 (absent)
        """
        user_id = interaction.user.id
        
        try:
            # DB에서 학생 조회
            student = await self.db_service.get_student_by_discord_id(user_id)
            
            if not student:
                await interaction.response.send_message(
                    "❌ 등록되지 않은 사용자입니다.",
                    ephemeral=True
                )
                return
            
            already_responded = False
            if student.response_status == "absent" and student.response_time:
                response_time_utc = student.response_time if student.response_time.tzinfo else student.response_time.replace(tzinfo=timezone.utc)
                time_since_response = datetime.now(timezone.utc) - response_time_utc
                if time_since_response < timedelta(minutes=5):
                    already_responded = True
            
            if already_responded:
                await interaction.response.send_message(
                    f"✅ 이미 응답이 기록되어 있습니다: **🚶 잠시 자리 비움**\n"
                    f"💡 10분 후에 카메라가 여전히 OFF 상태면 다시 알림을 받게 됩니다.",
                    ephemeral=True
                )
                return
            
            await self.db_service.record_response(student.id, action)
            await self.db_service.set_absent_reminder(student.id)
            
            await interaction.response.send_message(
                f"✅ 응답이 기록되었습니다: **🚶 잠시 자리 비움**\n"
                f"강사님께 알림이 전송됩니다.\n"
                f"💡 10분 후에 카메라가 여전히 OFF 상태면 다시 알림을 받게 됩니다.",
                ephemeral=True
            )
            
            # 강사 채널에 알림 (첫 번째 응답만)
            await self._notify_instructor(student, action)
            
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ 응답 처리 중 오류가 발생했습니다.",
                ephemeral=True
            )
    
    async def _handle_camera_check(self, interaction: discord.Interaction):
        """
        카메라 켬 버튼 응답 처리
        
        Args:
            interaction: Discord Interaction 객체
        """
        user_id = interaction.user.id
        
        try:
            # DB에서 학생 조회
            student = await self.db_service.get_student_by_discord_id(user_id)
            
            if not student:
                await interaction.response.send_message(
                    "❌ 등록되지 않은 사용자입니다.",
                    ephemeral=True
                )
                return
            
            if student.is_cam_on:
                await interaction.response.send_message(
                    f"✅ **카메라 확인 완료!**\n\n"
                    f"📷 현재 상태: **카메라 ON** 🟢\n"
                    f"💡 정상적으로 카메라가 켜져 있습니다. 계속 진행하세요!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ **카메라가 꺼져 있습니다!**\n\n"
                    f"📷 현재 상태: **카메라 OFF** 🔴\n"
                    f"⚠️ ZEP에서 카메라를 켜주세요!\n\n"
                    f"💡 카메라를 켠 후 다시 이 버튼을 눌러 확인하세요.",
                    ephemeral=True
                )
        
        except Exception as e:
            await interaction.response.send_message(
                "❌ 카메라 상태 확인 중 오류가 발생했습니다.",
                ephemeral=True
            )
    
    async def _notify_instructor(self, student, action: str):
        """
        관리자들에게 학생 응답 알림 DM 전송

        Args:
            student: Student 객체
            action: 응답 유형
        """
        try:
            # 관리자 목록 가져오기
            admin_ids = admin_manager.get_ids()
            if not admin_ids:
                return

            action_text = "🚶 잠시 자리 비움"
            action_emoji = "🚶"

            embed = discord.Embed(
                title=f"{action_emoji} 학생 응답 알림",
                description=f"**{student.zep_name}** 학생이 응답했습니다.",
                color=discord.Color.blue()
            )

            embed.add_field(name="응답 내용", value=action_text, inline=True)
            embed.add_field(name="카메라 상태", value="🔴 OFF", inline=True)
            embed.add_field(
                name="재알림 예정",
                value="10분 후",
                inline=True
            )

            # 각 관리자에게 개별 DM 전송
            for admin_id in admin_ids:
                try:
                    user = await self.fetch_user(admin_id)
                    if user:
                        await user.send(embed=embed)
                except Exception:
                    continue

        except Exception:
            pass
    
    async def send_camera_alert_to_admin(self, student):
        """
        관리자들에게 카메라 OFF 알림 DM 전송 (재알림 시)

        Args:
            student: Student 객체
        """
        try:
            # 관리자 목록 가져오기
            admin_ids = admin_manager.get_ids()
            if not admin_ids:
                return

            if not student.last_status_change:
                return

            last_change_utc = student.last_status_change if student.last_status_change.tzinfo else student.last_status_change.replace(tzinfo=timezone.utc)
            elapsed_minutes = int((datetime.now(timezone.utc) - last_change_utc).total_seconds() / 60)

            embed = discord.Embed(
                title="⚠️ 카메라 OFF 확인 요청",
                description=f"{student.zep_name}님의 카메라가 {elapsed_minutes}분째 꺼져 있습니다.",
                color=discord.Color.red()
            )

            embed.add_field(
                name="👤 학생",
                value=f"{student.zep_name}",
                inline=True
            )

            embed.add_field(
                name="⏱️ 카메라 OFF",
                value=f"{elapsed_minutes}분",
                inline=True
            )

            embed.add_field(
                name="📷 상태",
                value="카메라 OFF 🔴",
                inline=True
            )

            embed.add_field(
                name="💡 안내",
                value="학생에게 이미 1회 알림이 전송되었습니다.\n아래 버튼으로 외출/조퇴 여부를 확인하거나 학생에게 직접 확인하세요.",
                inline=False
            )

            # 각 관리자에게 개별 DM 전송 (각 메시지마다 새 View 생성 필요)
            for admin_id in admin_ids:
                try:
                    user = await self.fetch_user(admin_id)
                    if user:
                        # 각 메시지마다 새로운 View 인스턴스 생성
                        view = AdminLeaveView(student.id)
                        await user.send(embed=embed, view=view)
                except Exception:
                    # 특정 관리자에게 DM 실패해도 다른 관리자에게는 계속 시도
                    continue

        except Exception:
            pass
    
    async def send_leave_alert_to_admin(self, student):
        """
        관리자들에게 접속 종료 알림 DM 전송 (외출/조퇴 확인 요청)

        Args:
            student: Student 객체
        """
        try:
            # 관리자 목록 가져오기
            admin_ids = admin_manager.get_ids()
            if not admin_ids:
                return

            if not student.last_leave_time:
                return

            # 경과 시간 계산
            last_leave_time_utc = student.last_leave_time if student.last_leave_time.tzinfo else student.last_leave_time.replace(tzinfo=timezone.utc)
            elapsed_minutes = int((datetime.now(timezone.utc) - last_leave_time_utc).total_seconds() / 60)

            embed = discord.Embed(
                title="⚠️ 접속 종료 확인 요청",
                description=f"{student.zep_name}님이 접속을 종료한 지 {elapsed_minutes}분이 지났습니다.",
                color=discord.Color.orange()
            )

            embed.add_field(
                name="👤 학생",
                value=f"{student.zep_name}",
                inline=True
            )

            embed.add_field(
                name="⏱️ 경과 시간",
                value=f"{elapsed_minutes}분",
                inline=True
            )

            embed.add_field(
                name="💡 안내",
                value="아래 버튼으로 외출/조퇴 여부를 확인해주세요.\n확인하지 않으면 학생에게 DM이 전송됩니다.",
                inline=False
            )

            # 각 관리자에게 개별 DM 전송 (각 메시지마다 새 View 생성 필요)
            for admin_id in admin_ids:
                try:
                    user = await self.fetch_user(admin_id)
                    if user:
                        # 각 메시지마다 새로운 View 인스턴스 생성
                        view = AdminLeaveView(student.id)
                        await user.send(embed=embed, view=view)
                except Exception:
                    # 특정 관리자에게 DM 실패해도 다른 관리자에게는 계속 시도
                    continue

        except Exception:
            pass
    
    async def send_absent_alert(self, student) -> bool:
        """
        외출/조퇴 상태인 학생에게 알림 DM 전송
        
        Args:
            student: Student 객체
            
        Returns:
            전송 성공 여부
        """
        try:
            if not student.last_leave_time:
                return False

            user = await self.fetch_user(student.discord_id)

            # 경과 시간 계산
            last_leave_time_utc = student.last_leave_time if student.last_leave_time.tzinfo else student.last_leave_time.replace(tzinfo=timezone.utc)
            elapsed_minutes = int((datetime.now(timezone.utc) - last_leave_time_utc).total_seconds() / 60)
            absent_type_text = "외출" if student.absent_type == "leave" else "조퇴"
            
            embed = discord.Embed(
                title=f"⚠️ {absent_type_text} 확인",
                description=f"{student.zep_name}님, 접속 종료 후 {elapsed_minutes}분이 지났습니다.",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="📅 접속 종료 시간",
                value=f"{elapsed_minutes}분 전",
                inline=True
            )
            
            embed.add_field(
                name="📋 상태",
                value=f"{absent_type_text}",
                inline=True
            )
            
            embed.add_field(
                name="💡 안내",
                value="아래 버튼으로 상황을 확인해주세요.\n외출/조퇴를 선택하면 오늘 하루 알림이 전송되지 않습니다.",
                inline=False
            )
            
            view = StudentAbsentView(student.id)
            await user.send(embed=embed, view=view)
            
            return True
            
        except discord.Forbidden:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - 사용자가 DM을 차단했거나 Discord 봇과 서버를 공유하지 않습니다"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
        except discord.NotFound:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - Discord 사용자를 찾을 수 없습니다"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
        except Exception as e:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - {type(e).__name__}: {str(e)}"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
    
    async def _handle_admin_absent_response(self, interaction: discord.Interaction, custom_id: str):
        """
        관리자 외출/조퇴 응답 처리
        
        Args:
            interaction: Discord Interaction 객체
            action: "admin_leave" (외출) 또는 "admin_early_leave" (조퇴)
        """
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 버튼은 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return
        
        try:
            student_id = int(custom_id.split("_")[-1])
            student = await self.db_service.get_student_by_id(student_id)
            
            if not student:
                await interaction.response.send_message(
                    "❌ 학생을 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 외출/조퇴 상태 설정
            absent_type = "leave" if custom_id.startswith("admin_leave_") else "early_leave"
            await self.db_service.set_absent_status(student.id, absent_type)
            
            absent_type_text = "외출" if absent_type == "leave" else "조퇴"
            
            await interaction.response.send_message(
                f"✅ {student.zep_name}님의 상태가 **{absent_type_text}**로 설정되었습니다.\n"
                f"오늘 하루 동안 알림이 전송되지 않습니다.",
                ephemeral=True
            )
            
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ 응답 처리 중 오류가 발생했습니다.",
                ephemeral=True
            )
    
    async def _handle_student_absent_response(self, interaction: discord.Interaction, custom_id: str):
        """
        학생 외출/조퇴 응답 처리
        
        Args:
            interaction: Discord Interaction 객체
            action: "student_leave" (외출) 또는 "student_early_leave" (조퇴)
        """
        user_id = interaction.user.id
        
        try:
            # DB에서 학생 조회
            student = await self.db_service.get_student_by_discord_id(user_id)
            
            if not student:
                await interaction.response.send_message(
                    "❌ 등록되지 않은 사용자입니다.",
                    ephemeral=True
                )
                return
            
            # 외출/조퇴 상태 설정
            absent_type = "leave" if custom_id.startswith("student_leave_") else "early_leave"
            await self.db_service.set_absent_status(student.id, absent_type)
            
            absent_type_text = "외출" if absent_type == "leave" else "조퇴"
            
            await interaction.response.send_message(
                f"✅ 상태가 **{absent_type_text}**로 설정되었습니다.\n"
                f"오늘 하루 동안 알림이 전송되지 않습니다.",
                ephemeral=True
            )
            
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ 응답 처리 중 오류가 발생했습니다.",
                ephemeral=True
            )
    
    async def _handle_admin_check_student(self, interaction: discord.Interaction, custom_id: str):
        """
        관리자 "수강생 확인" 버튼 처리
        학생에게 DM을 보내서 외출/조퇴/복귀 버튼이 있는 메시지 전송
        
        Args:
            interaction: Discord Interaction 객체
            custom_id: "admin_check_student_{student_id}"
        """
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 버튼은 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return
        
        try:
            student_id = int(custom_id.split("_")[-1])
            student = await self.db_service.get_student_by_id(student_id)
            
            if not student:
                await interaction.response.send_message(
                    "❌ 학생을 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            if not student.discord_id:
                await interaction.response.send_message(
                    f"❌ {student.zep_name}님의 Discord ID가 등록되지 않았습니다.",
                    ephemeral=True
                )
                return

            user = await self.fetch_user(student.discord_id)

            # 경과 시간 계산: 퇴장한 경우 last_leave_time, 아니면 last_status_change 사용
            if student.last_leave_time:
                ref_time = student.last_leave_time if student.last_leave_time.tzinfo else student.last_leave_time.replace(tzinfo=timezone.utc)
                status_text = "접속 종료"
            elif student.last_status_change:
                ref_time = student.last_status_change if student.last_status_change.tzinfo else student.last_status_change.replace(tzinfo=timezone.utc)
                status_text = "카메라 OFF"
            else:
                await interaction.response.send_message(
                    f"❌ {student.zep_name}님의 상태 정보가 없습니다.",
                    ephemeral=True
                )
                return

            elapsed_minutes = int((datetime.now(timezone.utc) - ref_time).total_seconds() / 60)

            embed = discord.Embed(
                title="⚠️ 상태 확인",
                description=f"{student.zep_name}님, {status_text} 후 {elapsed_minutes}분이 지났습니다.",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="⏱️ 경과 시간",
                value=f"{elapsed_minutes}분",
                inline=True
            )
            
            embed.add_field(
                name="💡 안내",
                value="아래 버튼으로 상황을 확인해주세요.",
                inline=False
            )
            
            view = StudentAbsentView(student.id)
            
            try:
                await user.send(embed=embed, view=view)
                await interaction.response.send_message(
                    f"✅ {student.zep_name}님에게 확인 메시지를 전송했습니다.",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    f"❌ {student.zep_name}님에게 DM을 보낼 수 없습니다. (DM 차단 또는 친구 관계 필요)",
                    ephemeral=True
                )

        except Exception as e:
            print(f"❌ [Discord] 관리자 수강생 확인 처리 실패: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            await interaction.response.send_message(
                f"❌ 처리 중 오류가 발생했습니다: {type(e).__name__}",
                ephemeral=True
            )
    
    async def _handle_student_return(self, interaction: discord.Interaction, custom_id: str):
        """
        학생 "복귀" 버튼 처리
        ZEP으로 돌아오라는 메시지 전송
        
        Args:
            interaction: Discord Interaction 객체
            custom_id: "student_return_{student_id}"
        """
        user_id = interaction.user.id
        
        try:
            # DB에서 학생 조회
            student = await self.db_service.get_student_by_discord_id(user_id)
            
            if not student:
                await interaction.response.send_message(
                    "❌ 등록되지 않은 사용자입니다.",
                    ephemeral=True
                )
                return
            
            await self.db_service.record_return_request(student.id)
            
            await interaction.response.send_message(
                "🏠 **ZEP으로 돌아와주세요!**\n\n"
                "수업이 진행 중입니다. 가능한 한 빨리 ZEP에 접속해주시기 바랍니다.\n\n"
                f"💡 {config.RETURN_REMINDER_TIME}분 내에 접속하지 않으면 다시 알림을 받게 됩니다.",
                ephemeral=True
            )
            
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ 처리 중 오류가 발생했습니다.",
                ephemeral=True
            )
    
    async def send_return_reminder(self, student) -> bool:
        """
        복귀 요청 후 미접속 학생에게 재알림 DM 전송
        
        Args:
            student: Student 객체
            
        Returns:
            전송 성공 여부
        """
        try:
            if not student.last_return_request_time:
                return False

            user = await self.fetch_user(student.discord_id)

            # 경과 시간 계산
            last_return_time_utc = student.last_return_request_time if student.last_return_request_time.tzinfo else student.last_return_request_time.replace(tzinfo=timezone.utc)
            elapsed_minutes = int((datetime.now(timezone.utc) - last_return_time_utc).total_seconds() / 60)
            
            embed = discord.Embed(
                title="⚠️ 복귀 확인 요청",
                description=f"{student.zep_name}님, 복귀 요청 후 {elapsed_minutes}분이 지났습니다.",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="⏱️ 경과 시간",
                value=f"{elapsed_minutes}분",
                inline=True
            )
            
            embed.add_field(
                name="💡 안내",
                value="ZEP에 접속해주세요.\n아래 버튼으로 상황을 확인해주세요.",
                inline=False
            )
            
            view = StudentAbsentView(student.id)
            await user.send(embed=embed, view=view)
            
            return True
            
        except discord.Forbidden:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - 사용자가 DM을 차단했거나 Discord 봇과 서버를 공유하지 않습니다"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
        except discord.NotFound:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - Discord 사용자를 찾을 수 없습니다"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
        except Exception as e:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - {type(e).__name__}: {str(e)}"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
    
    async def send_manual_camera_alert(self, student) -> bool:
        """
        수동으로 카메라 켜주세요 DM 전송 (기존 send_camera_alert 재사용)
        
        Args:
            student: Student 객체
            
        Returns:
            전송 성공 여부
        """
        return await self.send_camera_alert(student)
    
    async def send_manual_join_request(self, student) -> bool:
        """
        수동으로 접속해 주세요 DM 전송
        
        Args:
            student: Student 객체
            
        Returns:
            전송 성공 여부
        """
        try:
            user = await self.fetch_user(student.discord_id)
            
            embed = discord.Embed(
                title="⚠️ 접속 확인 요청",
                description=f"{student.zep_name}님, ZEP에 접속해주세요.",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="💡 안내",
                value="ZEP에 접속해주시기 바랍니다.",
                inline=False
            )
            
            await user.send(embed=embed)
            return True
            
        except discord.Forbidden:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - 사용자가 DM을 차단했거나 Discord 봇과 서버를 공유하지 않습니다"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
        except discord.NotFound:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - Discord 사용자를 찾을 수 없습니다"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
        except Exception as e:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - {type(e).__name__}: {str(e)}"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
    
    async def send_face_not_visible_alert(self, student) -> bool:
        """
        화면에 얼굴이 안보여요 DM 전송
        
        Args:
            student: Student 객체
            
        Returns:
            전송 성공 여부
        """
        try:
            user = await self.fetch_user(student.discord_id)
            
            embed = discord.Embed(
                title="⚠️ 카메라 확인 요청",
                description=f"{student.zep_name}님, 젭 화면에 얼굴이 보이지 않습니다.",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="💡 안내",
                value="카메라 확인해 주시고 조정해 주세요!",
                inline=False
            )
            
            await user.send(embed=embed)
            return True
            
        except discord.Forbidden:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - 사용자가 DM을 차단했거나 Discord 봇과 서버를 공유하지 않습니다"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
        except discord.NotFound:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - Discord 사용자를 찾을 수 없습니다"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False
        except Exception as e:
            error_msg = f"❌ DM 전송 실패: {student.zep_name}님 (Discord ID: {student.discord_id}) - {type(e).__name__}: {str(e)}"
            print(f"❌ [Discord] {error_msg}")
            # 웹페이지 로그에도 표시
            try:
                from api.websocket_manager import manager
                asyncio.create_task(manager.broadcast_system_log(
                    level="error",
                    source="discord",
                    event_type="dm_failed",
                    message=error_msg,
                    student_name=student.zep_name,
                    student_id=student.id
                ))
            except Exception:
                pass
            return False


class AlertView(discord.ui.View):
    """알림 메시지용 인터랙티브 버튼"""
    
    def __init__(self):
        super().__init__(timeout=None)
        
        camera_on_button = discord.ui.Button(
            label="카메라 켬!",
            style=discord.ButtonStyle.success,
            custom_id="camera_on",
            emoji="📷"
        )
        self.add_item(camera_on_button)
        
        absent_button = discord.ui.Button(
            label="잠시 자리 비움 (10분 후 재알림)",
            style=discord.ButtonStyle.primary,
            custom_id="absent",
            emoji="🚶"
        )
        self.add_item(absent_button)


class AdminLeaveView(discord.ui.View):
    """관리자 접속 종료 알림용 인터랙티브 버튼"""

    def __init__(self, student_id: int):
        super().__init__(timeout=None)

        # 수강생 확인 버튼만 표시
        check_button = discord.ui.Button(
            label="수강생 확인",
            style=discord.ButtonStyle.success,
            custom_id=f"admin_check_student_{student_id}",
            emoji="👤"
        )
        self.add_item(check_button)


class StudentAbsentView(discord.ui.View):
    """학생 외출/조퇴 알림용 인터랙티브 버튼"""
    
    def __init__(self, student_id: int):
        super().__init__(timeout=None)
        
        leave_button = discord.ui.Button(
            label="외출",
            style=discord.ButtonStyle.primary,
            custom_id=f"student_leave_{student_id}",
            emoji="🚪"
        )
        self.add_item(leave_button)
        
        # 버튼 2: 조퇴
        early_leave_button = discord.ui.Button(
            label="조퇴",
            style=discord.ButtonStyle.danger,
            custom_id=f"student_early_leave_{student_id}",
            emoji="🏃"
        )
        self.add_item(early_leave_button)
        
        return_button = discord.ui.Button(
            label="복귀",
            style=discord.ButtonStyle.success,
            custom_id=f"student_return_{student_id}",
            emoji="🏠"
        )
        self.add_item(return_button)

