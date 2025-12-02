# 🎓 ZEP 학생 모니터링 시스템

ZEP 온라인 교육 환경에서 학생들의 카메라 상태를 실시간으로 모니터링하고, Discord를 통해 자동 알림을 보내는 풀스택 시스템입니다.

## 🏗️ 시스템 구조

```
ZEP → Slack 채널 → Python (Socket Mode) → Discord 알림
                    ↓
              FastAPI 백엔드 → React 프론트엔드 (웹 대시보드)
```

**왜 Slack을 거치나요?**

- ZEP Free/Basic Plan은 Discord 직접 연동 불가
- Slack만 Webhook 지원
- Slack Socket Mode로 실시간 감지 (1-2초 지연)

## ✨ 주요 기능

### 백엔드 기능

- ✅ **실시간 모니터링**: 카메라 ON/OFF 자동 감지 (1-2초 지연)
- ✅ **스마트 알림 (다단계 DM 시스템)**:
  - 1차 (22분 후): 수강생에게만 DM 전송
  - 2차+ (32분, 42분...): 수강생 + 관리자 모두에게 DM 전송
  - 알림 간격: 10분 쿨다운 (백엔드 재시작 시에도 유지)
- ✅ **인터랙티브 버튼**: 학생 응답 수집 (카메라 켬!/자리 비움)
- ✅ **외출/조퇴/휴가/결석 관리**:
  - Slack에서 외출/조퇴/휴가/결석 상태 자동 감지
  - 관리자가 수동으로 상태 설정 가능
  - 복귀 시 자동 재활성화
  - 외출/조퇴는 "퇴장"으로 분류, 휴가/결석은 "특이사항"으로 분류
- ✅ **접속 종료 감지**: 30분 이상 미복귀 시 관리자에게 알림
- ✅ **터미널 단축키**: 실시간 상태 확인 (Enter, o, l, n, p, r, q)
- ✅ **화면 모니터링** (선택): OCR + 얼굴 감지로 실제 출석 확인
- ✅ **관리자 권한**: 특정 사용자만 관리 명령어 사용 (관리자는 모니터링 제외)
- ✅ **재시작 복원**: 프로그램 재시작 시 과거 상태 자동 복원 (쿨다운 타이머 유지)
- ✅ **공휴일 자동 감지**: 주말/공휴일 자동 일시정지 (한국 공휴일 지원)

### 프론트엔드 기능

- ✅ **웹 대시보드**: 실시간 학생 상태 모니터링 (WebSocket 실시간 업데이트)
- ✅ **로그 뷰어**: 실시간 로그 스트리밍 (정확한 시간 표시)
- ✅ **학생 관리**: 학생 등록, 수정, 삭제, 상태 배지 표시
- ✅ **설정 관리**: Discord, Slack, 모니터링 설정, 동기화 버튼
- ✅ **통계 및 리포트**: 출석률, 카메라 상태 통계
- ✅ **자동 재연결**: 백엔드 재시작 시 자동 WebSocket 재연결 (health check 기반)

## 🚀 빠른 시작

### Docker Compose로 실행 (권장)

> 💡 **참고**: Docker를 사용하면 가상환경(venv)을 따로 만들거나 활성화할 필요가 없습니다. Docker 컨테이너 내부에서 필요한 패키지가 이미 설치되어 실행됩니다.

```bash
# 환경변수 설정
cd Back
cp .env.example .env
nano .env  # 또는 원하는 에디터

# 루트 디렉토리로 돌아가기
cd ..

# Docker Compose로 실행
docker-compose up -d
```

웹 대시보드: http://localhost:80
API 서버: http://localhost:8000

**Docker 사용 시 장점:**

- ✅ 가상환경(venv) 설정 불필요
- ✅ Python 버전 자동 관리
- ✅ 의존성 충돌 없음
- ✅ 백엔드와 프론트엔드 자동 연동
- ✅ 프로덕션 환경과 동일한 실행 환경

#### 로그 확인

```bash
# 모든 서비스 로그 확인
docker-compose logs

# 실시간 로그 확인 (tail -f)
docker-compose logs -f

# 특정 서비스만 로그 확인
docker-compose logs backend    # 백엔드만
docker-compose logs frontend   # 프론트엔드만

# 최근 100줄만 보기
docker-compose logs --tail=100

# 컨테이너 이름으로 직접 확인
docker logs auto_monitor_backend
docker logs auto_monitor_frontend
```

#### 기타 Docker 명령어

```bash
# 컨테이너 상태 확인
docker-compose ps

# 컨테이너 중지
docker-compose stop

# 컨테이너 중지 및 제거
docker-compose down

# 컨테이너 재시작 (기존 이미지 사용)
docker-compose restart

# ⭐ 코드 변경 후 재빌드 (중요!)
docker-compose up -d --build

# 특정 서비스만 재빌드
docker-compose up -d --build backend   # 백엔드만
docker-compose up -d --build frontend  # 프론트엔드만
```

### 로컬 개발 환경

#### 백엔드 설정

```bash
cd Back

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows

# 패키지 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
nano .env
```

#### 프론트엔드 설정

```bash
cd Front

# 패키지 설치
npm install

# 개발 서버 실행
npm run dev
```

#### 환경변수 설정

**Back/.env 파일:**

```env
# Discord
DISCORD_BOT_TOKEN=your_discord_bot_token
INSTRUCTOR_CHANNEL_ID=instructor_channel_id

# Slack
SLACK_BOT_TOKEN=xoxb-your_token
SLACK_APP_TOKEN=xapp-your_token
SLACK_CHANNEL_ID=C01234567

# 모니터링 설정
CAMERA_OFF_THRESHOLD=22        # 카메라 OFF 알림 임계값 (분)
ALERT_COOLDOWN=10              # 알림 쿨다운 시간 (분)
CHECK_INTERVAL=60              # 모니터링 체크 간격 (초)
LEAVE_ALERT_THRESHOLD=30       # 접속 종료 알림 임계값 (분)
DAILY_RESET_TIME=09:00         # 일일 초기화 시간 (HH:MM)

# 수업 시간 설정
CLASS_START_TIME=09:00
CLASS_END_TIME=18:00
LUNCH_START_TIME=12:00
LUNCH_END_TIME=13:00
```

#### 실행

```bash
# 백엔드 실행 (Back 디렉토리에서)
cd Back
python3 main.py

# 프론트엔드 실행 (별도 터미널, Front 디렉토리에서)
cd Front
npm run dev
```

## 📚 사용 방법

### Discord 명령어

| 명령어                            | 설명             | 권한        |
| --------------------------------- | ---------------- | ----------- |
| `!register [ZEP이름]`             | 학생 등록        | 모든 사용자 |
| `!status`                         | 내 상태 확인     | 모든 사용자 |
| `!admin_register [ZEP이름] @유저` | 다른 사용자 등록 | 관리자      |
| `!list_students`                  | 학생 목록 조회   | 관리자      |
| `!help`                           | 도움말           | 모든 사용자 |

### 웹 대시보드

- **대시보드**: 실시간 학생 현황 (카메라 ON/OFF/퇴장/특이사항)
- **학생 관리**: 학생 등록, 수정, 삭제, 일괄 가져오기, 상태별 필터링
- **로그 뷰어**: 실시간 모니터링 로그 (정확한 시간 표시, WebSocket 자동 재연결)
- **설정**:
  - 모니터링 설정 (임계값, 쿨다운 시간, 점심시간 등)
  - Slack 동기화 버튼 (수동 상태 동기화)
  - DM 일시정지/재개
  - 무시할 키워드 관리
- **통계**: 출석률 및 카메라 상태 통계

### 터미널 단축키 (백엔드 실행 중)

| 단축키           | 설명                                |
| ---------------- | ----------------------------------- |
| `Enter` 또는 `s` | 전체 학생 상태 요약                 |
| `o`              | 카메라 OFF 학생 상세 (경과 시간 표시) |
| `l`              | 접속 종료 학생 상세 (경과 시간 표시)  |
| `n`              | 오늘 미접속 학생 상세 (특이사항)     |
| `p`              | DM 알림 일시정지                    |
| `r`              | DM 알림 재개                        |
| `q`              | 프로그램 종료                       |
| `h`              | 도움말 표시                         |

## 🛠️ 기술 스택

### 백엔드

- Python 3.10+ (asyncio)
- FastAPI (REST API + WebSocket)
- Slack Bolt (Socket Mode)
- Discord.py
- SQLAlchemy (Async) + aiosqlite
- OpenCV (선택적)
- Tesseract OCR (선택적)

### 프론트엔드

- React 19
- TypeScript
- Vite
- Tailwind CSS
- Radix UI
- Zustand (상태 관리)
- React Router

### 인프라

- Docker & Docker Compose
- Nginx (프론트엔드 서빙)

## 📁 프로젝트 구조

```
Auto_monitor/
├── Back/                    # 백엔드 (Python)
│   ├── main.py              # 메인 엔트리 포인트
│   ├── config.py            # 환경변수 관리
│   ├── requirements.txt     # 패키지 목록
│   ├── .env                 # 환경변수 (수동 생성)
│   ├── api/                 # FastAPI 서버
│   │   ├── server.py        # FastAPI 앱
│   │   ├── routes/          # API 라우트
│   │   ├── schemas/         # Pydantic 스키마
│   │   └── websocket_manager.py
│   ├── database/            # 데이터베이스 모듈
│   │   ├── connection.py    # DB 연결
│   │   ├── models.py        # 모델 정의
│   │   └── db_service.py    # CRUD 작업
│   ├── services/            # 서비스 모듈
│   │   ├── slack_listener.py   # Slack 리스닝
│   │   ├── discord_bot.py      # Discord Bot
│   │   ├── monitor_service.py  # 모니터링 루프
│   │   └── screen_monitor.py   # 화면 모니터링 (선택)
│   ├── scripts/             # 유틸리티 스크립트
│   └── GUIDE.md             # 상세 가이드
├── Front/                   # 프론트엔드 (React)
│   ├── src/
│   │   ├── components/      # React 컴포넌트
│   │   ├── pages/           # 페이지 컴포넌트
│   │   ├── services/        # API 서비스
│   │   ├── hooks/           # 커스텀 훅
│   │   ├── stores/          # Zustand 스토어
│   │   └── types/           # TypeScript 타입
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml       # Docker Compose 설정
├── Dockerfile               # 통합 Docker 이미지
└── README.md               # 이 파일
```

## 📖 상세 문서

자세한 내용은 **[Back/GUIDE.md](./Back/GUIDE.md)** 를 참조하세요:

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
- 프로덕션 환경에서는 HTTPS를 사용하세요

## 📄 라이선스

MIT License

---

**Made with ❤️ for Better Online Education**
