# 🚀 Railpack 배포 가이드

## 환경변수 설정 방법

### 1. Railpack 대시보드 접속
1. [Railpack 웹사이트](https://railpack.com)에 로그인
2. 배포한 프로젝트 선택

### 2. 환경변수 설정 페이지로 이동
- 프로젝트 페이지에서 **"Settings"** 또는 **"설정"** 탭 클릭
- **"Environment Variables"** 또는 **"환경변수"** 섹션 찾기
- 또는 프로젝트 설정 메뉴에서 **"Variables"** 또는 **"환경변수"** 선택

### 3. 환경변수 추가
**"Add Variable"** 또는 **"변수 추가"** 버튼을 클릭하여 다음 환경변수들을 추가하세요:

## 필수 환경변수

### Discord 설정
```
DISCORD_BOT_TOKEN=your_discord_bot_token_here
```
- Discord Bot Token (Discord Developer Portal에서 발급)
- 예: `MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.XXXXXX.XXXXXXXXXXXXX`

```
INSTRUCTOR_CHANNEL_ID=your_channel_id
```
- 강사 채널 ID (선택사항, Discord 개발자 모드에서 확인)
- 예: `123456789012345678`

```
ADMIN_USER_IDS=123456789012345678,987654321098765432
```
- 관리자 Discord ID (쉼표로 구분, 선택사항)
- 비워두면 모든 사용자가 관리자 권한 보유

### Slack 설정
```
SLACK_BOT_TOKEN=xoxb-your-bot-token
```
- Slack Bot User OAuth Token (xoxb-로 시작)
- Slack App 설정에서 발급

```
SLACK_APP_TOKEN=xapp-your-app-token
```
- Slack App-Level Token (xapp-로 시작)
- Socket Mode 활성화에 필요

```
SLACK_CHANNEL_ID=C01234567
```
- ZEP 메시지를 받는 Slack 채널 ID
- 채널 우클릭 → "Copy link" → URL에서 ID 추출

## 선택적 환경변수 (기본값 사용 가능)

### 모니터링 설정
```
CAMERA_OFF_THRESHOLD=20
```
- 카메라 OFF 알림 임계값 (분)
- 기본값: 20분

```
ALERT_COOLDOWN=60
```
- 알림 쿨다운 시간 (분)
- 기본값: 60분

```
CHECK_INTERVAL=60
```
- 상태 체크 간격 (초)
- 기본값: 60초

### 수업 시간 설정
```
CLASS_START_TIME=10:10
CLASS_END_TIME=18:40
LUNCH_START_TIME=11:50
LUNCH_END_TIME=12:50
```

### 접속 종료 모니터링
```
LEAVE_ALERT_THRESHOLD=30
```
- 접속 종료 후 알림까지 시간 (분)
- 기본값: 30분

### 화면 모니터링 (선택사항)
```
SCREEN_MONITOR_ENABLED=false
SCREEN_CHECK_INTERVAL=1800
FACE_DETECTION_THRESHOLD=3
```

### 일일 초기화
```
DAILY_RESET_TIME=00:00
```
- 일일 초기화 시간 (HH:MM 형식)
- 비워두면 비활성화

## 환경변수 설정 후

1. **저장**: 모든 환경변수를 추가한 후 **"Save"** 또는 **"저장"** 클릭
2. **재배포**: 환경변수 변경 후 프로젝트를 재배포하거나 재시작
   - Railpack이 자동으로 재배포할 수도 있음
   - 또는 수동으로 "Redeploy" 버튼 클릭

## 확인 방법

배포 후 로그에서 다음 메시지들을 확인하세요:
- ✅ Discord Bot 준비 완료
- ✅ Slack 연결 완료 (Socket Mode)
- ✅ API 서버 시작

## 문제 해결

### 환경변수가 적용되지 않는 경우
1. 환경변수 이름이 정확한지 확인 (대소문자 구분)
2. 프로젝트 재배포 확인
3. Railpack 로그에서 환경변수 로드 오류 확인

### Discord/Slack 연결 실패
1. 토큰이 올바른지 확인
2. Bot 권한이 올바르게 설정되었는지 확인
3. Slack App Token이 Socket Mode로 설정되었는지 확인

