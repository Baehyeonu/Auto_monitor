"""
Shared system helpers to avoid duplicated API route logic.
"""
from __future__ import annotations


async def get_joined_today(timeout: int = 2) -> set[int]:
    """Return the set of student IDs that joined today."""
    try:
        from api.routes.settings import wait_for_system_instance
    except Exception:
        return set()

    system = await wait_for_system_instance(timeout=timeout)
    if system and system.slack_listener:
        return system.slack_listener.get_joined_students_today()
    return set()
