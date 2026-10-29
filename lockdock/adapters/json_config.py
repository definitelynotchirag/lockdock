"""modes.json: parse into core Config, hot-reload on mtime change."""
from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Callable
from pathlib import Path

from ..core.agents import DEFAULT_KINDS, merge_kinds
from ..core.models import DEFAULT_BROWSERS, Config, Mode, NotificationRules

EXAMPLE = Path(__file__).resolve().parents[2] / "modes.example.json"


def config_from_dict(raw: dict) -> Config:
    """Build a Config from parsed modes.json. Raises KeyError/ValueError on bad input."""
    modes = []
    for m in raw["modes"]:
        n = m.get("notifications", {})
        modes.append(Mode(
            id=m["id"], label=m.get("label", m["id"].title()), icon=m.get("icon", "●"),
            color=m.get("color", "#f0a04b"), description=m.get("description", ""),
            apps=m.get("apps", []), on_task=m.get("on_task", []), off_task=m.get("off_task", []),
            unknown=m.get("unknown", "ask"), off_task_action=m.get("off_task_action", "nudge"),
            notifications=NotificationRules(
                allow_from=n.get("allow_from", []), hold_from=n.get("hold_from", []),
                pass_keywords=n.get("pass_keywords", []), default=n.get("default", "hold")),
            exit_delay_s=int(m.get("exit_delay_s", 0)), per_press_s=int(m.get("per_press_s", 0)),
            on_enter=m.get("on_enter", []), on_exit=m.get("on_exit", []),
        ))
    llm = raw.get("llm", {})
    return Config(modes=modes, default_mode=raw.get("default_mode", modes[0].id),
                  llm_enabled=llm.get("enabled", True), llm_model=llm.get("model", "haiku"),
                  dwell_s=float(raw.get("dwell_s", 2.0)),
                  browsers=raw.get("browsers", list(DEFAULT_BROWSERS)),
                  agent_kinds=(merge_kinds(DEFAULT_KINDS, raw["agents"].get("kinds", []))
                               if isinstance(raw.get("agents"), dict) else None))


class JsonConfigLoader:
    """ConfigSource for ~/.config/lockdock/modes.json (seeded from modes.example.json)."""

    def __init__(self, path: Path, example: Path = EXAMPLE, poll_s: float = 2.0) -> None:
        self.path = path
        self.example = example
        self.poll_s = poll_s
        self._mtime = 0.0

    def load(self) -> Config:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(self.example, self.path)
        self._mtime = self.path.stat().st_mtime
        return config_from_dict(json.loads(self.path.read_text()))

    async def watch(self, on_change: Callable[[Config], None],
                    on_error: Callable[[Exception], None] | None = None) -> None:
        """Poll the mtime; on a change, load and hand the new Config to on_change."""
        while True:
            await asyncio.sleep(self.poll_s)
            try:
                mt = self.path.stat().st_mtime
            except OSError:
                continue
            if mt == self._mtime:
                continue
            self._mtime = mt
            try:
                cfg = self.load()
            except (ValueError, KeyError, OSError) as e:
                if on_error:
                    on_error(e)
                continue
            on_change(cfg)
