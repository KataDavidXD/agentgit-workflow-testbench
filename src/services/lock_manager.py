from __future__ import annotations

import asyncio


class LockManager:
    """Each env_id corresponds to an asyncio.Lock."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def get_lock(self, env_id: str) -> asyncio.Lock:
        if env_id not in self._locks:
            self._locks[env_id] = asyncio.Lock()
        return self._locks[env_id]

    async def cleanup_lock(self, env_id: str) -> None:
        if env_id in self._locks:
            lock = self._locks[env_id]
            if not lock.locked():
                self._locks.pop(env_id, None)

