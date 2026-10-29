"""events.jsonl: every verdict with its reason. The tuning agent reads this."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from .ports import Clock


class EventSink(Protocol):
    """Anything that records events (EventLog, or a list-backed fake in tests)."""

    def log(self, kind: str, **data: Any) -> None: ...


class EventLog:
    """Appends one JSON line per event, stamped with the time and the current mode."""

    def __init__(self, path: Path, clock: Clock, mode: Callable[[], str]) -> None:
        self.path = path
        self.clock = clock
        self.mode = mode

    def log(self, kind: str, **data: Any) -> None:
        rec = {"ts": round(self.clock.now(), 3), "kind": kind, "mode": self.mode(), **data}
        with self.path.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
