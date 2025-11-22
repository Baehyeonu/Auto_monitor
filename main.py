"""
Railpack 배포를 위한 메인 엔트리 포인트
Back/main.py를 실행합니다.
"""
import sys
import os
from pathlib import Path

# Back 디렉토리를 Python 경로에 추가
root_dir = Path(__file__).parent
back_dir = root_dir / "Back"

if not back_dir.exists():
    print("❌ Back directory not found!")
    sys.exit(1)

# Back 디렉토리로 이동하고 실행
os.chdir(back_dir)
sys.path.insert(0, str(back_dir))

# Back/main.py 실행
if __name__ == "__main__":
    # main.py를 모듈로 import하여 실행
    import importlib.util
    main_path = back_dir / "main.py"
    spec = importlib.util.spec_from_file_location("back_main", main_path)
    main_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main_module)

