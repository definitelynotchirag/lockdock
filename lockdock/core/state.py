"""The state.json snapshot the dock renders, with pluggable extension sections."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .models import Config, Notification, PendingSwitch

SectionProvider = Callable[[], "dict | list | int"]

CORE_SECTIONS: frozenset[str] = frozenset(
    {"mode", "modes", "pending", "activity", "held", "held_count", "updated_ms"})
# reserved extension points and their empty defaults
RESERVED_SECTIONS: dict[str, Callable[[], Any]] = {"agents": list, "pet": dict, "theme": dict,
                                                   "prompts": list, "prompts_count": int}
HELD_IN_SNAPSHOT = 50


class StateSnapshot:
    """Builds the state dict. Features add top-level sections with `register_section`."""

    def __init__(self) -> None:
        self._sections: dict[str, SectionProvider] = {}

    def register_section(self, name: str, provider: SectionProvider) -> None:
        """Publish `provider()` under `name` in every snapshot. Core keys cannot be replaced."""
        if name in CORE_SECTIONS:
            raise ValueError(f"'{name}' is a core state section")
        self._sections[name] = provider

    def build(self, *, cfg: Config, mode: str, pending: PendingSwitch | None, activity: dict,
              held: list[Notification], now: float) -> dict:
        st: dict[str, Any] = {
            "mode": mode,
            "modes": [{"id": m.id, "label": m.label, "icon": m.icon, "color": m.color,
                       "apps": m.apps, "description": m.description} for m in cfg.modes],
            "pending": ({"mode": pending.mode, "deadline_ms": int(pending.deadline * 1000),
                         "total_ms": int(pending.total * 1000)} if pending else None),
            "activity": activity,
            "held": [n.short() for n in held[-HELD_IN_SNAPSHOT:]],
            "held_count": len(held),
        }
        for name, empty in RESERVED_SECTIONS.items():
            st[name] = empty()
        for name, provider in self._sections.items():
            st[name] = provider()
        st["updated_ms"] = int(now * 1000)
        return st
