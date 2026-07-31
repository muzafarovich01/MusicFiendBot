from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class TaskManager:
    """Limits expensive jobs and deduplicates work by key."""

    def __init__(self, max_parallel: int = 2) -> None:
        self._sem = asyncio.Semaphore(max(1, max_parallel))
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._active = 0
        self._waiting = 0
        self._guard = asyncio.Lock()
        self._last_request: dict[int, float] = {}

    async def enter(self, key: str):
        return _JobContext(self, key)

    async def position(self) -> int:
        async with self._guard:
            return self._waiting + 1

    async def allow_user(self, user_id: int, cooldown: float = 1.2) -> tuple[bool, float]:
        now = time.monotonic()
        last = self._last_request.get(user_id, 0.0)
        remaining = cooldown - (now - last)
        if remaining > 0:
            return False, remaining
        self._last_request[user_id] = now
        return True, 0.0

    @property
    def active(self) -> int:
        return self._active

    @property
    def waiting(self) -> int:
        return self._waiting


class _JobContext:
    def __init__(self, manager: TaskManager, key: str) -> None:
        self.manager = manager
        self.key = key
        self.lock: asyncio.Lock | None = None

    async def __aenter__(self):
        self.lock = self.manager._locks[self.key]
        async with self.manager._guard:
            self.manager._waiting += 1
        await self.lock.acquire()
        await self.manager._sem.acquire()
        async with self.manager._guard:
            self.manager._waiting -= 1
            self.manager._active += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        async with self.manager._guard:
            self.manager._active -= 1
        self.manager._sem.release()
        if self.lock and self.lock.locked():
            self.lock.release()
        return False
