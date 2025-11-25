"""
설정 값의 지속성을 관리하는 유틸리티
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

PERSISTED_FIELDS: Dict[str, str] = {
    "camera_off_threshold": "CAMERA_OFF_THRESHOLD",
    "alert_cooldown": "ALERT_COOLDOWN",
    "check_interval": "CHECK_INTERVAL",
    "leave_alert_threshold": "LEAVE_ALERT_THRESHOLD",
    "class_start_time": "CLASS_START_TIME",
    "class_end_time": "CLASS_END_TIME",
    "lunch_start_time": "LUNCH_START_TIME",
    "lunch_end_time": "LUNCH_END_TIME",
    "daily_reset_time": "DAILY_RESET_TIME",
}

SETTINGS_FILE = Path(__file__).parent.parent / "data" / "settings.json"


def load_persisted_settings(config) -> None:
    """디스크에 저장된 설정 값을 불러와 Config 인스턴스에 적용"""
    if not SETTINGS_FILE.exists():
        return

    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return

    for field, attr in PERSISTED_FIELDS.items():
        if field in data:
            try:
                setattr(config, attr, data[field])
            except Exception:
                continue


def save_persisted_settings(config, extra_values: Dict[str, Any] | None = None) -> None:
    """현재 Config 값을 디스크에 저장"""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    payload: Dict[str, Any] = {}
    for field, attr in PERSISTED_FIELDS.items():
        payload[field] = getattr(config, attr, None)

    if extra_values:
        payload.update(extra_values)

    SETTINGS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


