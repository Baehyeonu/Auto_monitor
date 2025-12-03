# 🎓 ZEP 학생 모니터링 시스템

ZEP 온라인 교육 환경에서 학생들의 카메라 상태를 실시간으로 모니터링하고 Discord DM으로 자동 알림을 보내는 시스템입니다.

## 🏗️ 시스템 구조

```
ZEP → Slack → Python (Socket Mode) → Discord DM
              ↓
        FastAPI 백엔드 → React 웹 대시보드
```

## ✨ 주요 기능

- **실시간 모니터링**: 카메라 ON/OFF 자동 감지 (1-2초 지연)
- **스마트 알림**: 1차(22분) 학생 DM → 2차+(32분, 42분...) 학생+관리자 DM
- **상태 관리**: 지각/외출/조퇴/휴가/결석 자동 감지 및 수동 설정
- **웹 대시보드**: 실시간 학생 현황, 로그 뷰어, 통계
- **관리자 권한**: 특정 사용자만 관리 기능 사용
- **자동 복원**: 재시작 시 과거 상태 복원 (쿨다운 타이머 유지)

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# .env 파일 생성 및 설정
cp .env.example .env
nano .env  # Discord/Slack 토큰 입력
```

### 2. Docker로 실행 (권장)

```bash
docker-compose up -d
```

- 웹 대시보드: http://localhost:80
- API 서버: http://localhost:8000

### 3. 로컬 개발 환경

**백엔드:**

```bash
cd Back
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

**프론트엔드:**

```bash
cd Front
npm install
npm run dev
```

## 📚 사용 방법

### 학생 일괄 등록 (CSV)

프로젝트 루트에 `students.csv` 파일을 두면 프로그램 시작 시 자동으로 등록됩니다.

```bash
# students.csv.example을 복사하여 사용
cp students.csv.example students.csv
nano students.csv  # 학생 정보 입력
```

**CSV 형식:**
```csv
zep_name,discord_id
홍길동,123456789012345678
김철수,234567890123456789
이영희,
```

- Discord ID가 없으면 비워두고 나중에 웹 대시보드에서 추가 가능
- 이미 등록된 학생은 자동으로 스킵

### 웹 대시보드

- **대시보드**: 실시간 학생 현황 (카메라 ON/OFF/퇴장/특이사항)
- **학생 관리**: 등록, 수정, 삭제, 상태 설정, 관리자 지정
- **로그**: 실시간 모니터링 로그 (WebSocket 자동 재연결)
- **설정**: 모니터링 임계값, 수업 시간, Slack 동기화, DM 제어

## 🛠️ 기술 스택

**백엔드**: Python 3.10+, FastAPI, Slack Bolt, Discord.py, SQLAlchemy
**프론트엔드**: React 19, TypeScript, Vite, Tailwind CSS, Zustand
**인프라**: Docker, Docker Compose, Nginx

## 🔧 환경 변수

필수 설정은 `.env` 파일에서 관리하고, 나머지는 웹 대시보드에서 설정합니다.

**`.env` 파일 (필수):**

- `DISCORD_BOT_TOKEN`: Discord Bot 토큰
- `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL_ID`: Slack 연동 정보
- `DATABASE_URL`: 데이터베이스 경로

**웹 대시보드에서 설정:**

- 관리자 계정
- 모니터링 임계값 (카메라 OFF, 퇴장 알림 시간)
- 수업 시간 (시작/종료/점심/초기화 시간)

## 📁 주요 파일

```
Auto_monitor/
├── Back/                    # Python 백엔드
│   ├── main.py              # 메인 엔트리
│   ├── config.py            # 설정 관리
│   ├── api/                 # FastAPI 서버
│   ├── database/            # DB 모델/CRUD
│   └── services/            # Slack, Discord, 모니터링 서비스
├── Front/                   # React 프론트엔드
│   └── src/
│       ├── components/      # UI 컴포넌트
│       ├── pages/           # 페이지
│       └── services/        # API 호출
├── docker-compose.yml
└── .env.example
```
