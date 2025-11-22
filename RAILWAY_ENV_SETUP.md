# Railway 환경변수 설정 가이드

## ⚠️ 중요: Railway 환경변수 설정 형식

Railway 환경변수는 **주석 없이** `KEY=VALUE` 형식만 사용해야 합니다.

## ❌ 잘못된 예시

```
# Discord 설정
DISCORD_BOT_TOKEN=your_token_here  # 주석 포함 (X)
```

## ✅ 올바른 예시

```
DISCORD_BOT_TOKEN=your_token_here
```

## Railway에 설정해야 할 필수 환경변수

Railway Variables 탭에서 "New Variable" 버튼을 클릭하여 다음을 **주석 없이** 설정하세요:

### 1. DISCORD_BOT_TOKEN
- **변수 이름**: `DISCORD_BOT_TOKEN`
- **변수 값**: Discord Bot Token (주석 제거, 값만 입력)
- 예시 형식: `your-discord-bot-token-here` (실제 토큰으로 교체)

### 2. SLACK_BOT_TOKEN
- **변수 이름**: `SLACK_BOT_TOKEN`
- **변수 값**: Slack Bot Token (xoxb-로 시작)
- 예시 형식: `xoxb-your-actual-bot-token-here` (실제 토큰으로 교체)

### 3. SLACK_APP_TOKEN
- **변수 이름**: `SLACK_APP_TOKEN`
- **변수 값**: Slack App Token (xapp-로 시작)
- 예시 형식: `xapp-your-actual-app-token-here` (실제 토큰으로 교체)

### 4. SLACK_CHANNEL_ID
- **변수 이름**: `SLACK_CHANNEL_ID`
- **변수 값**: Slack 채널 ID
- 예: `C01234567`

## 선택적 환경변수 (기본값 사용 가능)

### INSTRUCTOR_CHANNEL_ID
- **변수 이름**: `INSTRUCTOR_CHANNEL_ID`
- **변수 값**: Discord 채널 ID (선택사항)
- 예: `123456789012345678`

### ADMIN_USER_IDS
- **변수 이름**: `ADMIN_USER_IDS`
- **변수 값**: 관리자 Discord ID (쉼표로 구분, 선택사항)
- 예: `123456789012345678,987654321098765432`

## Railway 설정 방법

1. Railway 대시보드 → 프로젝트 선택
2. **Variables** 탭 클릭
3. **"+ New Variable"** 버튼 클릭
4. **변수 이름** 입력 (예: `DISCORD_BOT_TOKEN`)
5. **변수 값** 입력 (주석 없이 값만, 예: `MTIzNDU2Nzg5...`)
6. **저장**
7. 나머지 환경변수도 동일하게 반복
8. 모든 환경변수 설정 후 **"Redeploy"** 클릭

## 주의사항

- ❌ 주석(`#`) 포함하지 마세요
- ❌ 빈 줄 포함하지 마세요
- ❌ `KEY=VALUE` 형식 외의 다른 형식 사용하지 마세요
- ✅ 값만 입력하세요
- ✅ 대소문자 정확히 일치해야 합니다

## 확인 방법

환경변수 설정 후 Railway 로그에서 다음 메시지가 보이면 성공:
```
✅ DISCORD_BOT_TOKEN: ********** (설정됨)
✅ SLACK_BOT_TOKEN: ********** (설정됨)
✅ SLACK_APP_TOKEN: ********** (설정됨)
✅ SLACK_CHANNEL_ID: ********** (설정됨)
```

