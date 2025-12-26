from __future__ import annotations

import asyncio
from collections import defaultdict


class LockManager:
    """Each node_id corresponds to an asyncio.Lock."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def get_lock(self, node_id: str) -> asyncio.Lock:
        return self._locks[node_id]

    async def cleanup_lock(self, node_id: str) -> None:
        self._locks.pop(node_id, None)

