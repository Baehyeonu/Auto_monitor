# 🎓 ZEP 학생 모니터링 시스템

ZEP 온라인 교육 환경에서 학생들의 카메라 상태를 실시간으로 모니터링하고, Discord를 통해 자동 알림을 보내는 시스템입니다.

## 🏗️ 시스템 구조

```
ZEP → Slack 채널 → Python (Socket Mode) → Discord 알림
```

**왜 Slack을 거치나요?**

- ZEP Free/Basic Plan은 Discord 직접 연동 불가
- Slack만 Webhook 지원
- Slack Socket Mode로 실시간 감지 (1-2초 지연)

## ✨ 주요 기능

- ✅ **실시간 모니터링**: 카메라 ON/OFF 자동 감지 (1-2초 지연)
- ✅ **스마트 알림**:
  - 1차: 학생에게 DM (20분 후)
  - 2차: 관리자 채널에 알림 (관리자 판단 후 처리)
- ✅ **인터랙티브 버튼**: 학생 응답 수집 (카메라 켬!/자리 비움)
- ✅ **외출/조퇴 관리**:
  - 관리자가 외출/조퇴 상태 설정
  - 복귀 시 자동 재활성화
- ✅ **접속 종료 감지**: 30분 이상 미복귀 시 알림
- ✅ **터미널 단축키**: 실시간 상태 확인 (Enter, o, l, n)
- ✅ **화면 모니터링** (선택): OCR + 얼굴 감지로 실제 출석 확인
- ✅ **관리자 권한**: 특정 사용자만 관리 명령어 사용 (관리자는 모니터링 제외)
- ✅ **재시작 복원**: 프로그램 재시작 시 과거 상태 자동 복원

## 🚀 빠른 시작 (15분)

### 1. 사전 준비

- Python 3.10 이상
- Discord 서버 + Bot 생성
- Slack 워크스페이스 관리자 권한
- ZEP → Slack 연동 확인

### 2. 설치

```bash
cd zep-monitor

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows

# 패키지 설치
pip install -r requirements.txt
```

### 3. 환경변수 설정

```bash
cp .env.example .env
nano .env  # 또는 원하는 에디터
```

**필수 설정:**

```env
# Discord
DISCORD_BOT_TOKEN=your_discord_bot_token
INSTRUCTOR_CHANNEL_ID=instructor_channel_id

# Slack
SLACK_BOT_TOKEN=xoxb-your_token
SLACK_APP_TOKEN=xapp-your_token
SLACK_CHANNEL_ID=C01234567

# 모니터링 설정
CAMERA_OFF_THRESHOLD=20
ALERT_COOLDOWN=60
```

### 4. 실행

```bash
python3 main.py
```

## 📚 사용 방법

### 학생 등록

Discord에서:

```
!register 홍길동
```

### 상태 확인

```
!status
```

### Discord 명령어

| 명령어                            | 설명             | 권한        |
| --------------------------------- | ---------------- | ----------- |
| `!register [ZEP이름]`             | 학생 등록        | 모든 사용자 |
| `!status`                         | 내 상태 확인     | 모든 사용자 |
| `!admin_register [ZEP이름] @유저` | 다른 사용자 등록 | 관리자      |
| `!list_students`                  | 학생 목록 조회   | 관리자      |
| `!help`                           | 도움말           | 모든 사용자 |

### 터미널 단축키 (프로그램 실행 중)

| 단축키           | 설명                              |
| ---------------- | --------------------------------- |
| `Enter` 또는 `s` | 전체 학생 상태 요약               |
| `o`              | 카메라 OFF 학생 상세              |
| `l`              | 접속 종료 학생 상세               |
| `n`              | 오늘 미접속 학생 상세 (휴가/병가) |
| `q`              | 프로그램 종료                     |
| `h`              | 도움말 표시                       |

## 🛠️ 기술 스택

- Python 3.10+ (asyncio)
- Slack Bolt (Socket Mode)
- Discord.py
- SQLAlchemy (Async) + aiosqlite
- OpenCV (선택적)
- Tesseract OCR (선택적)

## 📁 프로젝트 구조

```
zep-monitor/
├── main.py                 # 메인 엔트리 포인트
├── config.py               # 환경변수 관리
├── requirements.txt        # 패키지 목록
├── .env                    # 환경변수 (수동 생성)
├── database/               # 데이터베이스 모듈
│   ├── connection.py       # DB 연결
│   ├── models.py           # 모델 정의
│   └── db_service.py       # CRUD 작업
├── services/               # 서비스 모듈
│   ├── slack_listener.py   # Slack 리스닝
│   ├── discord_bot.py      # Discord Bot
│   ├── monitor_service.py  # 모니터링 루프
│   └── screen_monitor.py   # 화면 모니터링 (선택)
└── scripts/                # 유틸리티 스크립트
    └── add_student.py      # 수동 등록
```

## 📖 상세 문서

자세한 내용은 **[GUIDE.md](./GUIDE.md)** 를 참조하세요:

- 🔧 Discord/Slack Bot 생성 방법
- ⚙️ 환경변수 상세 설정
- 👥 관리자 권한 설정
- 📺 화면 모니터링 활성화
- 🐛 트러블슈팅
- 💡 최적화 팁

## 🔐 보안 주의사항

- `.env` 파일을 Git에 커밋하지 마세요
- Bot 토큰을 절대 공개하지 마세요
- 관리자 ID는 최소한으로 설정하세요

## 📄 라이선스

MIT License

---

**Made with ❤️ for Better Online Education**
