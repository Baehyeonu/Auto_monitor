#!/bin/bash
set -e

# 프론트엔드 빌드 스크립트 (Railpack 빌드 단계에서 실행)

if [ -d "Front" ]; then
    echo "📦 Building frontend..."
    cd Front
    
    # Node.js 확인
    if ! command -v node &> /dev/null; then
        echo "⚠️ Node.js not found. Skipping frontend build."
        exit 0
    fi
    
    # 의존성 설치
    if [ ! -d "node_modules" ]; then
        echo "📦 Installing frontend dependencies..."
        npm ci
    fi
    
    # 프로덕션 빌드 (API URL을 상대 경로로 설정)
    echo "🏗️ Building frontend for production..."
    export VITE_API_URL=""  # 상대 경로 사용
    export VITE_WS_URL=""    # 상대 경로 사용
    npm run build
    
    cd ..
    echo "✅ Frontend build completed!"
else
    echo "⚠️ Front directory not found. Skipping frontend build."
fi

