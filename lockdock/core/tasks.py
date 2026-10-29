"""Spawning background coroutines, injectable so tests can run without an event loop."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

Spawn = Callable[[Coroutine[Any, Any, None]], "asyncio.Task[None] | None"]


def spawn_task(coro: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
    """Schedule `coro` on the running loop."""
    return asyncio.get_running_loop().create_task(coro)
