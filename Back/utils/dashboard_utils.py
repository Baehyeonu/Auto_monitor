"""
Shared helpers for dashboard and monitoring logic.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable, Set
from zoneinfo import ZoneInfo


STATUS_TYPES: Set[str] = {
    "late",
    "leave",
    "early_leave",
    "vacation",
    "absence",
    "not_joined",
}


def has_special_status(student) -> bool:
    """Return True when a student is in a special status bucket."""
    return student.status_type in STATUS_TYPES


def is_not_joined(student, joined_today: Set[int]) -> bool:
    """
    Determine whether a student should be treated as "not joined".

    Rules:
    - Admins are excluded.
    - Special statuses are always treated as not joined.
    - Otherwise, joined_today membership decides.
    """
    if student.is_admin:
        return False
    if has_special_status(student):
        return True
    return student.id not in joined_today


def is_left_today(student, today_local: date | None = None) -> bool:
    """Return True if the student left today (Asia/Seoul 기준)."""
    if not student.last_leave_time:
        return False

    today = today_local or date.today()
    leave_time = student.last_leave_time
    if leave_time.tzinfo is None:
        leave_time_utc = leave_time.replace(tzinfo=timezone.utc)
    else:
        leave_time_utc = leave_time
    leave_time_local = leave_time_utc.astimezone(ZoneInfo("Asia/Seoul"))
    return leave_time_local.date() == today


def build_overview(
    students: Iterable,
    joined_today: Set[int],
    now_utc: datetime,
    threshold_minutes: int,
) -> dict:
    """Compute dashboard overview metrics."""
    non_admin_students = [s for s in students if not s.is_admin]
    today = date.today()

    camera_on = 0
    camera_off = 0
    left = 0
    not_joined = 0
    threshold_exceeded = 0

    for student in non_admin_students:
        has_status = has_special_status(student)

        if is_not_joined(student, joined_today):
            not_joined += 1

        if not has_status and is_left_today(student, today):
            left += 1

        if not has_status and student.id in joined_today and not student.last_leave_time:
            if student.is_cam_on:
                camera_on += 1
            else:
                camera_off += 1
                if student.last_status_change:
                    last_change_utc = student.last_status_change
                    if last_change_utc.tzinfo is None:
                        last_change_utc = last_change_utc.replace(tzinfo=timezone.utc)
                    elapsed = (now_utc - last_change_utc).total_seconds() / 60
                    if elapsed >= threshold_minutes:
                        threshold_exceeded += 1

    return {
        "total_students": len(non_admin_students),
        "camera_on": camera_on,
        "camera_off": camera_off,
        "left": left,
        "not_joined_today": not_joined,
        "threshold_exceeded": threshold_exceeded,
        "last_updated": now_utc.isoformat(),
    }
