"""
환경변수 설정 관리
"""
from pydantic_settings import BaseSettings
from typing import Optional, List


class Config(BaseSettings):
    """애플리케이션 설정"""
    
    # Discord 설정
    DISCORD_BOT_TOKEN: str
    INSTRUCTOR_CHANNEL_ID: Optional[str] = None
    ADMIN_USER_IDS: str = ""  # 관리자 Discord ID (쉼표로 구분, 예: "123456789,987654321")
    
    # Slack 설정
    SLACK_BOT_TOKEN: str
    SLACK_APP_TOKEN: str
    SLACK_CHANNEL_ID: str  # ZEP 메시지를 받는 Slack 채널 ID
    
    # 모니터링 설정
    CAMERA_OFF_THRESHOLD: int = 20  # 분
    ALERT_COOLDOWN: int = 60  # 분
    CHECK_INTERVAL: int = 60  # 초
    
    # 수업 시간 설정 (HH:MM 형식)
    CLASS_START_TIME: str = "10:10"  # 수업 시작 시간
    CLASS_END_TIME: str = "18:40"    # 수업 종료 시간
    LUNCH_START_TIME: str = "11:50"  # 점심 시작 시간
    LUNCH_END_TIME: str = "12:50"    # 점심 종료 시간
    
    # 자리 비움 재알림 시간
    ABSENT_REMINDER_TIME: int = 10  # 분 (자리 비움 선택 시 재알림까지 시간)
    
    # 접속 종료 모니터링 설정
    LEAVE_ALERT_THRESHOLD: int = 30  # 분 (접속 종료 후 알림까지 시간)
    LEAVE_ADMIN_ALERT_COOLDOWN: int = 60  # 분 (관리자 접속 종료 알림 쿨다운)
    ABSENT_ALERT_COOLDOWN: int = 30  # 분 (외출/조퇴 알림 쿨다운)
    RETURN_REMINDER_TIME: int = 5  # 분 (복귀 요청 후 재알림까지 시간)
    
    # 일일 초기화 설정
    DAILY_RESET_TIME: Optional[str] = None  # "HH:MM" 형식, 비우면 비활성화
    
    # 화면 모니터링 설정
    SCREEN_MONITOR_ENABLED: bool = False  # 화면 모니터링 활성화 여부
    SCREEN_CHECK_INTERVAL: int = 1800  # 초 (화면 체크 간격, 기본 30분)
    FACE_DETECTION_THRESHOLD: int = 3  # 명 (감지 차이가 이 이상이면 알림)
    
    # 데이터베이스
    DATABASE_URL: str = "sqlite+aiosqlite:///students.db"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    def get_admin_ids(self) -> List[int]:
        """
        관리자 ID 리스트 반환
        
        Returns:
            관리자 Discord ID 리스트
        """
        if not self.ADMIN_USER_IDS:
            return []
        
        try:
            # 쉼표로 구분된 ID 문자열을 리스트로 변환
            ids = [int(id.strip()) for id in self.ADMIN_USER_IDS.split(",") if id.strip()]
            return ids
        except ValueError:
            print("⚠️ ADMIN_USER_IDS 형식이 잘못되었습니다. 숫자를 쉼표로 구분해주세요.")
            return []


# 전역 설정 인스턴스
config = Config()

