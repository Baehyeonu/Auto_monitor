"""
관리자 권한 캐시 관리
"""
from typing import Set
import asyncio

from database import DBService


class AdminManager:
    def __init__(self):
        self._admin_ids: Set[int] = set()
        self._loaded = False
        self._lock = asyncio.Lock()

    async def refresh(self):
        """DB에서 관리자 목록을 다시 불러옴"""
        async with self._lock:
            ids = await DBService.get_admin_ids()
            self._admin_ids = {admin_id for admin_id in ids if admin_id is not None}
            self._loaded = True

    async def ensure_loaded(self):
        """한 번도 로드되지 않았다면 초기화"""
        if not self._loaded:
            await self.refresh()

    def is_admin(self, user_id: int) -> bool:
        """관리자 여부 확인 (관리자가 없으면 모두 허용)"""
        if not self._admin_ids:
            return True
        return user_id in self._admin_ids

    def get_ids(self):
        return list(self._admin_ids)


admin_manager = AdminManager()

