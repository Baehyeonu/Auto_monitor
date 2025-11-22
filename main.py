"""
Railpack 배포를 위한 메인 엔트리 포인트
프론트엔드 빌드 후 Back/main.py를 실행합니다.
"""
import sys
import os
import subprocess
from pathlib import Path


def build_frontend():
    """프론트엔드 빌드"""
    root_dir = Path(__file__).parent
    front_dir = root_dir / "Front"
    
    if not front_dir.exists():
        print("⚠️ Front directory not found. Skipping frontend build.")
        return False
    
    print("📦 Building frontend...")
    
    # Node.js 확인
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✅ Node.js found: {result.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ Node.js not found. Skipping frontend build.")
        return False
    
    # Front 디렉토리로 이동
    original_dir = os.getcwd()
    try:
        os.chdir(front_dir)
        
        # 의존성 설치
        if not (front_dir / "node_modules").exists():
            print("📦 Installing frontend dependencies...")
            subprocess.run(["npm", "ci"], check=True)
        else:
            print("✅ Frontend dependencies already installed")
        
        # 환경변수 설정 (상대 경로 사용)
        env = os.environ.copy()
        env["VITE_API_URL"] = ""  # 상대 경로 사용
        env["VITE_WS_URL"] = ""   # 상대 경로 사용
        
        # 프로덕션 빌드
        print("🏗️ Building frontend for production...")
        subprocess.run(["npm", "run", "build"], check=True, env=env)
        
        print("✅ Frontend build completed!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Frontend build failed: {e}")
        print("   Continuing with backend only...")
        return False
    finally:
        os.chdir(original_dir)


def main():
    """메인 실행 함수"""
    root_dir = Path(__file__).parent
    back_dir = root_dir / "Back"
    
    if not back_dir.exists():
        print("❌ Back directory not found!")
        sys.exit(1)
    
    # 1. 프론트엔드 빌드
    print("🚀 Starting Auto Monitor deployment...")
    build_frontend()
    
    # 2. 백엔드 실행
    print("\n🔧 Starting backend server...")
    os.chdir(back_dir)
    sys.path.insert(0, str(back_dir))
    
    # Back/main.py 실행
    import importlib.util
    main_path = back_dir / "main.py"
    spec = importlib.util.spec_from_file_location("back_main", main_path)
    main_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main_module)


if __name__ == "__main__":
    main()

