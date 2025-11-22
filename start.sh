#!/bin/bash
set -e

# Railpack에서 실행되는 스크립트
# 프론트엔드 빌드 후 백엔드 실행

echo "🚀 Starting Auto Monitor deployment..."

# 1. 프론트엔드 빌드
if [ -d "Front" ]; then
    echo "📦 Building frontend..."
    cd Front
    
    # Node.js가 설치되어 있는지 확인
    if ! command -v node &> /dev/null; then
        echo "⚠️ Node.js not found. Installing Node.js..."
        # Railpack 환경에서는 Node.js가 이미 설치되어 있을 수 있음
    fi
    
    # 의존성 설치
    if [ ! -d "node_modules" ]; then
        echo "📦 Installing frontend dependencies..."
        npm ci
    fi
    
    # 프로덕션 빌드 (API URL을 상대 경로로 설정)
    echo "🏗️ Building frontend for production..."
    # Railpack 환경에서는 같은 서버에서 서빙되므로 상대 경로 사용
    export VITE_API_URL=""  # 상대 경로 사용
    export VITE_WS_URL=""    # 상대 경로 사용
    npm run build
    
    cd ..
    echo "✅ Frontend build completed!"
else
    echo "⚠️ Front directory not found. Skipping frontend build."
fi

# 2. 백엔드 실행
cd Back

# Python 의존성 설치
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# 환경변수 파일 확인
if [ ! -f ".env" ]; then
    echo "⚠️ Warning: .env file not found. Please set environment variables."
fi

# 백엔드 서버 시작
echo "🚀 Starting backend server..."
python main.py
