# 📚 ZEP 모니터링 시스템 완벽 가이드

이 문서는 설치부터 고급 기능까지 모든 내용을 다룹니다.

## 📑 목차

1. [설치 가이드](#1-설치-가이드)
2. [환경변수 설정](#2-환경변수-설정)
3. [Bot 생성 방법](#3-bot-생성-방법)
4. [관리자 권한 설정](#4-관리자-권한-설정)
5. [화면 모니터링](#5-화면-모니터링)
6. [고급 기능](#6-고급-기능)
7. [트러블슈팅](#7-트러블슈팅)

---

## 1. 설치 가이드

### 시스템 요구사항

- **OS**: macOS / Linux / Windows
- **Python**: 3.10 이상
- **메모리**: 최소 2GB
- **네트워크**: 인터넷 연결 필수

### 설치 과정

#### 1-1. 저장소 클론

```bash
git clone <repository-url>
cd zep-monitor
```

#### 1-2. 가상환경 설정

```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

#### 1-3. 패키지 설치

```bash
pip install -r requirements.txt
```

**설치되는 패키지:**

- `slack-bolt` - Slack Socket Mode
- `discord.py` - Discord Bot
- `sqlalchemy[asyncio]` - 비동기 DB
- `aiosqlite` - SQLite 비동기 드라이버
- `pydantic-settings` - 환경변수 관리
- `python-dotenv` - .env 파일 로드
- `opencv-python` (선택) - 화면 모니터링
- `pytesseract` (선택) - OCR
- `mss`, `pillow`, `numpy` (선택) - 이미지 처리

---

## 2. 환경변수 설정

### 2-1. .env 파일 생성

```bash
cp .env.example .env
nano .env  # 또는 code .env
```

### 2-2. 필수 설정

```env
# ===== Discord 설정 =====
# Discord Bot Token (https://discord.com/developers/applications)
DISCORD_BOT_TOKEN=your_discord_bot_token

# 강사 채널 ID (개발자 모드 → 채널 우클릭 → ID 복사)
INSTRUCTOR_CHANNEL_ID=123456789012345678

# 관리자 Discord ID (쉼표로 구분, 선택적)
# 비워두면 모든 사용자가 관리자
ADMIN_USER_IDS=123456789012345678,987654321098765432

# ===== Slack 설정 =====
# Slack Bot User OAuth Token (xoxb-로 시작)
SLACK_BOT_TOKEN=xoxb-your_token_here

# Slack App-Level Token (xapp-로 시작)
SLACK_APP_TOKEN=xapp-your_token_here

# ZEP 메시지를 받는 Slack 채널 ID
# Slack 채널 정보 → 맨 아래 "채널 ID" 복사
SLACK_CHANNEL_ID=C01234567
```

### 2-3. 모니터링 설정

```env
# ===== 모니터링 기본 설정 =====
# 카메라 OFF 알림 임계값 (분)
CAMERA_OFF_THRESHOLD=20

# 재알림 쿨다운 (분)
ALERT_COOLDOWN=60

# 상태 체크 간격 (초)
CHECK_INTERVAL=60

# ===== 수업 시간 설정 =====
# HH:MM 형식
CLASS_START_TIME=10:10
CLASS_END_TIME=18:40
LUNCH_START_TIME=11:50
LUNCH_END_TIME=12:50

# ===== 접속 종료 모니터링 =====
# 접속 종료 후 알림까지 시간 (분)
LEAVE_ALERT_THRESHOLD=30

# 관리자 접속 종료 알림 쿨다운 (분)
LEAVE_ADMIN_ALERT_COOLDOWN=60

# 외출/조퇴 알림 쿨다운 (분)
ABSENT_ALERT_COOLDOWN=30

# 복귀 요청 후 재알림까지 시간 (분)
RETURN_REMINDER_TIME=5

# 자리 비움 재알림 시간 (분)
ABSENT_REMINDER_TIME=10

# ===== 일일 초기화 =====
# 매일 지정된 시각에 상태 초기화 (HH:MM 형식)
# 비워두면 비활성화
DAILY_RESET_TIME=09:00

# ===== 화면 모니터링 (선택) =====
# 활성화 여부
SCREEN_MONITOR_ENABLED=false

# 체크 간격 (초) - 1800 = 30분, 3600 = 1시간
SCREEN_CHECK_INTERVAL=1800

# 감지 차이 임계값 (명)
FACE_DETECTION_THRESHOLD=3

# ===== 데이터베이스 =====
DATABASE_URL=sqlite+aiosqlite:///students.db
```

### 2-4. 설정 설명

| 설정                    | 기본값 | 설명                             |
| ----------------------- | ------ | -------------------------------- |
| `CAMERA_OFF_THRESHOLD`  | 20     | 카메라 OFF 후 알림까지 시간 (분) |
| `ALERT_COOLDOWN`        | 60     | 재알림 대기 시간 (분)            |
| `CHECK_INTERVAL`        | 60     | 모니터링 체크 주기 (초)          |
| `LEAVE_ALERT_THRESHOLD` | 30     | 접속 종료 후 알림까지 시간 (분)  |
| `ABSENT_REMINDER_TIME`  | 10     | 자리 비움 재알림 시간 (분)       |
| `DAILY_RESET_TIME`      | None   | 일일 초기화 시각 (HH:MM)         |

**주의:** 설정 변경 후 프로그램 재시작 필요

---

## 3. Bot 생성 방법

### 3-1. Discord Bot 생성

#### Step 1: Developer Portal 접속

1. [Discord Developer Portal](https://discord.com/developers/applications) 접속
2. **"New Application"** 클릭
3. 이름 입력 (예: `ZEP Monitor`)

#### Step 2: Bot 설정

1. 좌측 메뉴 → **"Bot"**
2. **"Add Bot"** 클릭
3. **Intents 활성화:**
   - ✅ `MESSAGE CONTENT INTENT`
   - ✅ `SERVER MEMBERS INTENT`
4. **"Reset Token"** 클릭 → 토큰 복사
   - ⚠️ 이 토큰은 다시 볼 수 없으니 안전하게 보관!

#### Step 3: 서버에 초대

1. 좌측 메뉴 → **OAuth2 → URL Generator**
2. **Scopes 선택:**
   - ✅ `bot`
   - ✅ `applications.commands`
3. **Bot Permissions 선택:**
   - ✅ `Send Messages`
   - ✅ `Read Message History`
   - ✅ `Use Slash Commands`
   - ✅ `Embed Links`
4. 하단 URL 복사 → 브라우저에 붙여넣기
5. 테스트 서버 선택 → 권한 부여

#### Step 4: 채널 ID 확인

1. Discord 설정 → 고급 → **개발자 모드** 켜기
2. 강사 채널 우클릭 → **"ID 복사"**
3. `.env` 파일의 `INSTRUCTOR_CHANNEL_ID`에 입력

---

### 3-2. Slack Bot 생성

#### Step 1: 앱 생성

1. [Slack API](https://api.slack.com/apps) 접속
2. **"Create New App"** 클릭
3. **"From scratch"** 선택
4. App Name: `zep-monitor`
5. **Workspace 선택:** ZEP이 연동된 워크스페이스!

#### Step 2: Socket Mode 활성화

1. Settings → **Socket Mode**
2. **Enable Socket Mode** 토글 ON
3. Token Name: `app-token`
4. **Generate** 클릭
5. 토큰 복사 (`xapp-...`)
   - ⚠️ 이 토큰을 `.env`의 `SLACK_APP_TOKEN`에 입력

#### Step 3: Bot Token Scopes 추가

1. Features → **OAuth & Permissions**
2. Bot Token Scopes → **Add an OAuth Scope:**
   - ✅ `channels:history` - 채널 메시지 읽기
   - ✅ `channels:read` - 채널 정보 읽기
   - ✅ `chat:write` - 메시지 전송
   - ✅ `users:read` - 사용자 정보 읽기
   - ✅ `groups:history` - Private 채널 메시지 읽기
   - ✅ `groups:read` - Private 채널 정보 읽기

#### Step 4: Event Subscriptions 설정

1. Features → **Event Subscriptions**
2. **Enable Events** 토글 ON
3. Subscribe to bot events:
   - ✅ `message.channels` - 채널 메시지 이벤트
   - ✅ `message.groups` - Private 채널 메시지 이벤트

#### Step 5: 워크스페이스에 설치

1. Settings → **Install App**
2. **"Install to Workspace"** 클릭
3. **허용** 클릭
4. Bot User OAuth Token 복사 (`xoxb-...`)
   - ⚠️ 이 토큰을 `.env`의 `SLACK_BOT_TOKEN`에 입력

#### Step 6: ZEP 알림 채널에 추가

Slack 채널에서:

```
/invite @zep-monitor
```

✅ 채널 멤버 목록에 봇이 표시되면 성공!

#### Step 7: 채널 ID 확인

1. Slack 데스크톱/웹에서 ZEP 알림 채널 열기
2. 채널 이름 클릭 → 하단 정보 보기
3. 맨 아래 **"채널 ID"** 복사 (예: `C01234567`)
4. `.env`의 `SLACK_CHANNEL_ID`에 입력

---

## 4. 관리자 권한 설정

### 4-1. 관리자 전용 명령어

다음 명령어는 관리자만 사용 가능:

- `!admin_register` - 다른 사용자 강제 등록
- `!list_students` - 등록된 학생 목록 조회

### 4-2. 관리자 ID 확인

#### 방법 A: Discord 개발자 모드

1. Discord 설정 → 고급 → **개발자 모드** 켜기
2. 사용자 프로필 우클릭 → **"ID 복사"**

#### 방법 B: !status 명령어

Discord에서:

```
!status
```

자신의 ID가 표시됩니다.

### 4-3. .env 파일에 추가

```env
# 관리자 1명
ADMIN_USER_IDS=123456789012345678

# 관리자 여러 명 (쉼표로 구분)
ADMIN_USER_IDS=123456789012345678,987654321098765432,111222333444555666
```

**주의:**

- 쉼표(`,`)로 구분
- 공백 있어도 OK
- 따옴표 없이 숫자만

### 4-4. 프로그램 재시작

```bash
# Ctrl+C로 종료 후
python main.py
```

### 4-5. 테스트

**관리자 계정:**

```
!list_students
```

→ 학생 목록 표시

**일반 사용자:**

```
!list_students
```

→ "관리자만 사용 가능" 메시지

### 4-6. 관리자 미설정 시

`ADMIN_USER_IDS`를 비워두거나 삭제하면:

- ⚠️ **모든 사용자**가 관리자 명령어 사용 가능
- 하위 호환성 유지

---

## 5. 화면 모니터링

### 5-1. 개요

ZEP 화면을 주기적으로 캡처하여 실제 출석 확인

**작동 방식:**

```
1. Slack에서 카메라 ON 학생 명단 수집
   ↓
2. 30분마다 화면 캡처
   ↓
3. OCR + 얼굴 감지로 실제 출석 확인
   ↓
4. 차이 발생 시 강사 채널에 알림
```

**정확도:**

- OCR 기본: 40~50%
- - 전처리: 70~80%
- - 학생 명단 매칭: 85~95%
- - 여러 번 시도: 90~97%

### 5-2. 사전 준비

#### Tesseract OCR 설치

**macOS:**

```bash
brew install tesseract tesseract-lang
```

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-kor
```

**Windows:**

1. [Tesseract 다운로드](https://github.com/UB-Mannheim/tesseract/wiki)
2. 설치 시 **"Additional language data"** → **Korean** 선택
3. 환경변수 PATH에 추가 (예: `C:\Program Files\Tesseract-OCR`)

**설치 확인:**

```bash
tesseract --version
tesseract --list-langs  # kor가 있어야 함
```

### 5-3. 활성화 방법

`.env` 파일:

```env
# 화면 모니터링 활성화
SCREEN_MONITOR_ENABLED=true

# 체크 간격 (초) - 1800 = 30분
SCREEN_CHECK_INTERVAL=1800

# 감지 차이 임계값 (명)
FACE_DETECTION_THRESHOLD=3
```

### 5-4. 권한 설정

**macOS:**

- 시스템 환경설정 → 보안 및 개인정보 보호
- 개인정보 보호 → 화면 녹화
- Python/터미널 추가

**Windows:**

- 관리자 권한으로 실행

**Linux:**

- Wayland 사용 시 X11로 전환

### 5-5. 실행 및 확인

```bash
python main.py
```

**정상 시작 로그:**

```
👁️ Screen Monitor 초기화 중...
✅ 화면 모니터링 서비스 초기화 완료
...
• Screen Monitor: 🟢 활성화 (체크 간격: 1800초 / 30분)
```

**체크 로그 (30분마다):**

```
🔍 [14:30] 화면 체크 시작...
   📊 카메라 ON 학생: 20명
   🎯 화면에서 감지: 18명
   ✅ 정상 (차이: 2명, 임계값: 3명)
```

**문제 발생 시:**

```
🔍 [15:00] 화면 체크 시작...
   📊 카메라 ON 학생: 20명
   🎯 화면에서 감지: 16명
   ⚠️ 4명 부재 감지!
   ❌ 미감지 학생: 김영준, 이주한, 박진우, 최선호
   📢 강사 채널에 알림 전송 완료
```

### 5-6. 최적화 팁

**ZEP 설정:**

- 비디오 박스 크게
- 이름표 폰트 크게
- 전체화면 또는 최대화

**시스템 설정:**

- 화면 해상도 최대로
- 화면 밝기 적절히
- 반사 최소화

**추천 설정:**

```env
# 일반 수업 (30~40명)
SCREEN_CHECK_INTERVAL=1800    # 30분
FACE_DETECTION_THRESHOLD=3

# 소규모 수업 (10~20명)
SCREEN_CHECK_INTERVAL=2700    # 45분
FACE_DETECTION_THRESHOLD=2

# 엄격한 관리
SCREEN_CHECK_INTERVAL=900     # 15분
FACE_DETECTION_THRESHOLD=1
```

---

## 6. 고급 기능

### 6-1. 일일 초기화

매일 지정된 시각에 상태 자동 초기화

```env
DAILY_RESET_TIME=09:00
```

**초기화 항목:**

- 카메라 상태 (is_cam_on)
- 알림 기록 (last_alert_sent, alert_count)
- 접속 종료 상태 (last_leave_time, is_absent)
- 외출/조퇴 상태

**유지 항목:**

- 학생 등록 정보 (zep_name, discord_id)
- 생성 시간 (created_at)

### 6-2. 재시작 시 상태 복원

프로그램 재시작 시 Slack 메시지 히스토리를 조회하여 과거 상태 복원:

**복원 과정:**

1. 모든 학생 상태 초기화 (카메라 OFF, 접속 종료 해제)
2. 일일 초기화 시간 이후 Slack 메시지 조회 (pagination 처리)
3. 시간순으로 정렬
4. 카메라 ON/OFF, 입장/퇴장 이벤트 순서대로 처리
5. 현재 상태 복원
6. 알림 타이머 초기화 (재시작 시점부터 새로 카운트)

**주요 특징:**

- 오늘 접속하지 않은 학생은 "미접속" 상태로 자동 분류
- 어제 데이터는 무시 (일일 초기화 시간 이후만 조회)
- 역할명 포함 이름도 자동 파싱 ("주강사\_유승수" → "유승수")

**로그 예시:**

```
🔄 카메라 및 접속 상태 초기화 중...
   ✅ 모든 학생 카메라 상태 OFF로 초기화 완료
   🔄 2025-11-21 09:00 이후 메시지 히스토리 복원 중...
   📥 총 127개 메시지 조회 완료
   ✅ 복원 완료: 127개 이벤트 처리
      입장: 15, 퇴장: 12
      카메라 ON: 54, OFF: 46
   🔄 알림 타이머 초기화 중...
   ✅ 알림 타이머 초기화 완료
```

### 6-3. 터미널 단축키

프로그램 실행 중 터미널에서 실시간으로 상태 확인:

| 단축키  | 명령어        | 기능                                                            |
| ------- | ------------- | --------------------------------------------------------------- |
| `Enter` | `s`, `status` | **전체 학생 상태 요약** - 카메라 ON/OFF, 접속 종료, 미접속 통계 |
| `o`     | `off`         | **카메라 OFF 학생 상세** - 이름, 경과 시간, 임계값 초과 여부    |
| `l`     | `leave`       | **접속 종료 학생 상세** - 이름, 경과 시간, 외출/조퇴 상태       |
| `n`     | `not_joined`  | **오늘 미접속 학생 상세** - 이름, Discord 등록 여부             |
| `q`     | `quit`        | 프로그램 종료                                                   |
| `h`     | `help`        | 도움말 표시                                                     |

**출력 예시 (Enter 입력 시):**

```
============================================================
📊 학생 상태 (2025-11-21 16:50:00)
============================================================

   🟢 카메라 ON            : 22명
   🔴 카메라 OFF           : 3명 (⚠️ 임계값 초과: 2명)
   🚪 접속 종료            : 3명 (⚠️ 임계값 초과: 1명)
   ⚪ 미접속 (휴가/병가)   : 13명

   📊 총 등록              : 38명
   ⚠️  전체 임계값 초과    : 3명
============================================================
```

### 6-4. 스마트 알림 시스템

**2단계 알림 프로세스:**

1. **1차 알림 (학생 DM):**

   - 카메라 OFF 20분 경과
   - Discord DM 전송
   - 버튼: "카메라 켬!", "잠시 자리 비움"

2. **2차 알림 (관리자 채널):**
   - 쿨다운 경과 후에도 카메라 OFF 지속
   - 관리자 채널에만 알림 (학생에게 재전송 X)
   - 버튼: "외출", "조퇴", "수강생 확인"
   - 관리자 판단 후 처리

**외출/조퇴 자동 재활성화:**

- 외출 처리된 학생이 다시 입장하면 자동으로 모니터링 재개
- 조퇴 처리된 학생은 당일 종료로 간주

**관리자 제외:**

- 관리자로 등록된 Discord ID는 모니터링 대상에서 자동 제외
- 카메라 OFF 알림, 접속 종료 알림 미전송

### 6-5. 수업 시간 자동 인식

설정한 수업 시간에만 모니터링 작동:

```env
CLASS_START_TIME=10:10    # 수업 시작
CLASS_END_TIME=18:40      # 수업 종료
LUNCH_START_TIME=11:50    # 점심 시작
LUNCH_END_TIME=12:50      # 점심 종료
```

**자동 처리:**

- 수업 시작 전: 모니터링 안 함
- 점심 시간: 모니터링 안 함, 카메라 타이머 초기화
- 수업 종료 후: 모니터링 안 함

### 6-4. 접속 종료 모니터링

학생이 ZEP에서 나간 후 30분 경과 시:

1. 관리자에게 알림 (외출/조퇴 확인 요청)
2. 관리자가 외출/조퇴 선택 또는 학생에게 확인 요청
3. 학생에게 DM 전송 (외출/조퇴/복귀 선택)

**설정:**

```env
LEAVE_ALERT_THRESHOLD=30           # 30분 후 알림
LEAVE_ADMIN_ALERT_COOLDOWN=60     # 관리자 알림 쿨다운
ABSENT_ALERT_COOLDOWN=30          # 학생 알림 쿨다운
RETURN_REMINDER_TIME=5            # 복귀 재알림 시간
```

### 6-5. 터미널 단축키

프로그램 실행 중 사용 가능한 단축키:

| 입력        | 기능                |
| ----------- | ------------------- |
| `[Enter]`   | 전체 학생 상태 확인 |
| `o+[Enter]` | 카메라 OFF 학생만   |
| `l+[Enter]` | 접속 종료 학생만    |
| `n+[Enter]` | 접속 안 한 학생만   |
| `q+[Enter]` | 프로그램 종료       |
| `[Ctrl+C]`  | 강제 종료           |

---

## 7. 트러블슈팅

### 7-1. Slack 메시지 감지 안 됨

**증상:** ZEP에서 카메라 껐는데 Python 터미널에 아무 로그 없음

**체크리스트:**

- [ ] Socket Mode 활성화됨?
- [ ] Event Subscriptions에서 `message.channels`, `message.groups` 구독?
- [ ] Bot Token Scopes 6개 모두 추가?
- [ ] 워크스페이스에 재설치?
- [ ] `/invite @앱이름`으로 채널에 추가?
- [ ] `.env`의 `SLACK_CHANNEL_ID` 올바름?

**해결:**

1. Slack API → Settings → Install App
2. **Reinstall to Workspace** 클릭
3. 새 Bot Token 복사 → `.env` 업데이트
4. Python 재시작

### 7-2. Discord DM 전송 안 됨

**증상:** 20분 지났는데 DM 안 옴

**체크리스트:**

- [ ] `!register` 명령어로 등록?
- [ ] ZEP 이름과 등록 이름 정확히 일치?
- [ ] 쿨다운 중? (DB 초기화: `rm students.db`)
- [ ] Discord DM 허용 설정?

**해결:**

```bash
# 1. 등록 확인
!status

# 2. DB 초기화 (테스트용)
rm students.db
python main.py

# 3. 빠른 테스트 설정
# .env 파일:
CAMERA_OFF_THRESHOLD=1   # 1분
ALERT_COOLDOWN=5         # 5분
```

### 7-3. "Field required: SLACK_CHANNEL_ID" 오류

**증상:**

```
ValidationError: Field required
SLACK_CHANNEL_ID
```

**해결:**

1. `.env` 파일에 `SLACK_CHANNEL_ID` 추가:
   ```env
   SLACK_CHANNEL_ID=C01234567
   ```
2. Slack 채널 ID 확인 방법:
   - 채널 이름 클릭 → 하단 정보 → "채널 ID" 복사

### 7-4. 화면 모니터링 오류

**"Tesseract를 찾을 수 없습니다":**

```bash
# macOS
brew install tesseract tesseract-lang

# Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-kor

# Windows - 환경변수 추가
# C:\Program Files\Tesseract-OCR
```

**"화면 캡처 실패":**

- **macOS:** 화면 녹화 권한 부여 필요
- **Linux:** X11 사용 (Wayland 아님)
- **Windows:** 관리자 권한으로 실행

**OCR 인식률 낮음:**

- ZEP 화면 크게
- 이름표 폰트 크게
- 화면 해상도 높게
- 체크 간격 늘리기 (CPU 부담 감소)

### 7-5. 데이터베이스 초기화

**모든 데이터 삭제 후 재시작:**

```bash
rm students.db
python main.py
```

**학생 재등록 필요!**

### 7-6. 디버그 모드

더 자세한 로그 확인:

`services/slack_listener.py` 95번 줄 수정:

```python
text = event.get("text", "")
print(f"📨 Slack 메시지 수신: {text}")  # 이 줄 추가

# 카메라 ON 메시지
match_on = self.pattern_cam_on.search(text)
```

### 7-7. 관리자 권한 오류

**"이 명령어는 관리자만 사용할 수 있습니다":**

1. `.env` 파일 확인:

   ```bash
   cat .env | grep ADMIN_USER_IDS
   ```

2. 올바른 형식:

   ```env
   ADMIN_USER_IDS=123456789012345678
   ```

3. 잘못된 형식:

   ```env
   ADMIN_USER_IDS="123456789012345678"  # 따옴표 X
   ADMIN_USER_IDS=@username              # 이름 X
   ```

4. 프로그램 재시작 필요

### 7-8. 메모리 부족

**증상:** MemoryError 발생

**해결:**

```env
# 체크 간격 늘리기
SCREEN_CHECK_INTERVAL=3600  # 1시간

# 화면 모니터링 비활성화
SCREEN_MONITOR_ENABLED=false
```

---

## 📝 추가 정보

### 데이터베이스 구조

**students 테이블:**

| 필드               | 타입       | 설명             |
| ------------------ | ---------- | ---------------- |
| id                 | Integer    | 기본키           |
| zep_name           | String     | ZEP 이름 (고유)  |
| discord_id         | BigInteger | Discord 유저 ID  |
| is_cam_on          | Boolean    | 카메라 ON/OFF    |
| last_status_change | DateTime   | 마지막 상태 변경 |
| last_alert_sent    | DateTime   | 마지막 알림 시간 |
| alert_count        | Integer    | 알림 횟수        |
| response_status    | String     | 학생 응답 상태   |
| is_absent          | Boolean    | 외출/조퇴 여부   |
| last_leave_time    | DateTime   | 마지막 퇴장 시간 |

### 메시지 패턴

Slack에서 감지하는 메시지 형식:

```
[14:01] 📷 진창훈/IH02 님의 카메라가 on 되었습니다
[14:01] 🚫 현우_조교 님의 카메라가 off 되었습니다
[14:07] 🚫 이주한/IH02 님이 교실에서 접속을 종료했습니다.
[14:13] 👨‍💼 송일현/IH02 님이 교실에 접속했습니다.
```

### 보안 권장사항

1. **Bot 토큰 관리**

   - `.env` 파일을 Git에 커밋하지 마세요
   - 토큰을 절대 공개하지 마세요
   - 정기적으로 토큰 재발급

2. **관리자 권한**

   - 필요한 사람만 최소한으로
   - 퇴사자 즉시 제거
   - ID 정기 검토

3. **프로덕션 환경**
   - PostgreSQL/MySQL 사용 권장
   - 백업 정기 실행
   - 로그 모니터링

---

## 🎉 완료!

이제 ZEP 모니터링 시스템을 완벽하게 활용할 수 있습니다!

**문제가 있나요?**

- 트러블슈팅 섹션 확인
- GitHub Issues에 문의
- 로그 전체 복사 + 스크린샷 첨부

**Made with ❤️ for Better Online Education**
