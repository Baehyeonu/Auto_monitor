"""
Railpack FastAPI 자동 감지를 위한 app.py
Back/api/server.py의 app을 export합니다.
"""
import sys
from pathlib import Path

# Back 디렉토리를 Python 경로에 추가
root_dir = Path(__file__).parent
back_dir = root_dir / "Back"
sys.path.insert(0, str(back_dir))

# Back/api/server.py에서 app import
from api.server import app

# Railpack이 FastAPI를 감지하도록 app을 export
__all__ = ["app"]

