# 📝 변경 사항 (Changelog)

## v2.1.0 - 2025-11-21 (오후)

### ✨ 새로운 기능

#### ⌨️ 터미널 단축키 시스템
- 실시간 상태 요약 보기 (Enter)
- 카메라 OFF 학생 상세 보기 (o)
- 접속 종료 학생 상세 보기 (l)
- 미접속 학생 상세 보기 (n) - **NEW!**
- 깔끔한 통계 중심 UI

#### 🎯 스마트 알림 시스템
- **2단계 알림**: 1차 학생 DM → 2차 관리자 채널만
- 2차 알림 시 학생에게 재전송 하지 않음
- 관리자 선택지: 외출/조퇴/수강생 확인

#### 🔄 외출/조퇴 자동 재활성화
- 외출 처리 학생이 복귀하면 자동 모니터링 재개
- 카메라 ON 또는 입장 시 자동 감지

#### 👨‍💼 관리자 제외 기능
- 관리자로 등록된 사용자는 모니터링 대상에서 자동 제외
- 모든 알림 (카메라 OFF, 접속 종료 등) 미전송

#### 📊 미접속 학생 분리
- "카메라 OFF"와 "오늘 미접속" 명확히 구분
- 오늘 입장 기록이 없는 학생 별도 표시
- 휴가/병가 학생 구분 용이

### 🔧 개선사항

#### 🧠 이름 파싱 개선
- 역할명 포함 이름 자동 파싱 ("주강사_유승수" → "유승수")
- 여러 한글 이름 순차 매칭 시도

#### 🔄 재시작 시 상태 복원 개선
- 일일 초기화 시간 이후 메시지만 조회 (24시간 → 오늘만)
- 모든 학생 상태 초기화 후 복원
- 접속 종료 시간 초기화 (오늘 안 들어온 학생 알림 방지)

#### 🛑 Graceful Shutdown
- `RuntimeWarning: coroutine was never awaited` 에러 수정
- 프로그램 종료 시 모든 비동기 작업 정상 종료

### 🐛 버그 수정

#### Timezone 에러 17곳 수정
- `can't subtract offset-naive and offset-aware datetimes` 해결
- 모든 datetime 연산을 UTC timezone-aware로 통일
- 파일: `main.py`, `discord_bot.py`, `monitor_service.py`, `db_service.py`

#### 상태 초기화 문제
- 재시작 시 모든 학생 "OFF 후 0분" 표시 → 오늘 입장 기록 기반 분류
- 오늘 안 들어온 학생이 "카메라 OFF"로 표시 → "미접속"으로 분리
- 오늘 안 들어온 학생의 "접속 종료 알림" → 수정 완료

### 📚 문서 업데이트

- README.md: 터미널 단축키, 스마트 알림 시스템 추가
- GUIDE.md: 터미널 단축키 상세 설명, 2단계 알림 프로세스, 자동 재활성화 추가
- 재시작 시 상태 복원 섹션 업데이트

---

## v2.0.0 - 2025-11-21 (오전)

### ✨ 새로운 기능

#### 🔄 재시작 시 상태 복원
- Slack 메시지 히스토리 조회 (pagination 지원)
- 최근 24시간 이벤트 자동 복원
- 알림 타이머 초기화 (재시작 시점부터 새로 카운트)

#### 📺 화면 모니터링 시스템
- OCR + 얼굴 감지로 실제 출석 확인
- 학생 명단 매칭 (85~95% 정확도)
- 강사 채널에만 알림 (학생들 모름)
- 30분~1시간 간격 체크 (설정 가능)

#### 👥 접속 종료 모니터링
- 30분 이상 미복귀 시 알림
- 관리자 확인 (외출/조퇴 선택)
- 학생 DM (외출/조퇴/복귀 선택)

#### 🔐 관리자 권한 시스템
- 특정 사용자만 관리 명령어 사용
- Discord ID 기반 권한 관리
- 여러 관리자 지원

#### 🧹 일일 초기화
- 매일 지정된 시각 자동 초기화
- 학생 등록 정보 유지
- 알림/접속 상태만 초기화

### 🔧 개선사항

- Timezone 처리 헬퍼 함수 추가
- 코드 중복 제거 및 리팩토링
- 불필요한 함수 제거 (`get_db_session`)
- 에러 처리 개선
- 로그 메시지 정리

### 📚 문서 개선

- README.md - 간결한 메인 문서로 개편
- GUIDE.md - 통합 상세 가이드 신규 작성
- 중복 문서 정리 (QUICK_START, ADMIN_GUIDE, SCREEN_MONITOR_GUIDE 통합)

### 📦 새로운 패키지

```
opencv-python>=4.8.0        # 이미지 처리
mss>=9.0.1                  # 화면 캡처
pytesseract>=0.3.10         # OCR
pillow>=10.0.0              # 이미지 처리
numpy>=1.24.0               # 수치 연산
python-Levenshtein>=0.21.0  # 문자열 유사도
```

### 🔧 새로운 환경변수

```env
SLACK_CHANNEL_ID            # Slack 채널 ID (필수)
DAILY_RESET_TIME           # 일일 초기화 시간
ADMIN_USER_IDS             # 관리자 Discord ID
SCREEN_MONITOR_ENABLED     # 화면 모니터링 on/off
SCREEN_CHECK_INTERVAL      # 화면 체크 간격
FACE_DETECTION_THRESHOLD   # 감지 차이 임계값
LEAVE_ALERT_THRESHOLD      # 접속 종료 알림 시간
ABSENT_REMINDER_TIME       # 자리 비움 재알림 시간
```

### 🐛 버그 수정

- Slack 히스토리 조회 pagination 미처리 → 수정
- Timezone aware/naive datetime 혼용 → 통일
- 과거 메시지 무시로 인한 상태 손실 → 복원 기능 추가

---

## v1.0.0 - 2025-11-19

### ✨ 초기 릴리스

- Slack Socket Mode 연동
- Discord Bot 알림
- 카메라 ON/OFF 자동 감지
- 인터랙티브 버튼 (카메라 켬!/자리 비움)
- 강사 채널 알림
- 쿨다운 시스템
- SQLite 데이터베이스
- 학생 등록/조회 명령어

---

**Made with ❤️ for Better Online Education**
