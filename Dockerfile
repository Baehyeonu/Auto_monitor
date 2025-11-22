# 멀티 스테이지 빌드: 프론트엔드 + 백엔드 통합

# ============================================
# Stage 1: 프론트엔드 빌드
# ============================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# 프론트엔드 의존성 설치
COPY Front/package*.json ./
RUN npm ci

# 프론트엔드 소스 코드 복사 및 빌드
COPY Front/ ./
# API URL을 상대 경로로 설정하여 같은 서버에서 서빙
ENV VITE_API_URL=""
ENV VITE_WS_URL=""
RUN npm run build

# ============================================
# Stage 2: 백엔드 실행 환경
# ============================================
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치 (화면 캡처, OCR 등에 필요)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-kor \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY Back/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 백엔드 코드 복사
COPY Back/ .

# 프론트엔드 빌드 결과물 복사 (Stage 1에서)
COPY --from=frontend-builder /app/frontend/dist ./Front/dist

# 데이터베이스 디렉토리 생성
RUN mkdir -p /app/data

# 포트 노출
EXPOSE 8000

# 백엔드 서버 시작 (프론트엔드 정적 파일도 함께 서빙)
CMD ["python", "main.py"]

