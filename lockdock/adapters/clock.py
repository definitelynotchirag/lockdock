"""The real clock."""
from __future__ import annotations

import asyncio
import time


class SystemClock:
    """Clock port backed by time.time and asyncio.sleep."""

    def now(self) -> float:
        return time.time()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
