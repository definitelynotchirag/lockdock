"""JSON config files (modes.json, pet.json): seed from an example, parse, hot-reload on mtime change."""
from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, Generic, TypeVar

from ..core.models import DEFAULT_BROWSERS, Config, Mode, NotificationRules

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "modes.example.json"
PET_EXAMPLE = ROOT / "pet.example.json"
T = TypeVar("T")


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
                  browsers=raw.get("browsers", list(DEFAULT_BROWSERS)))


class JsonConfigLoader(Generic[T]):
    """ConfigSource for a JSON file seeded from an example on first run.

    Defaults to ~/.config/lockdock/modes.json -> Config; pass `parse` for another
    file (pet.json uses `pet_config_from_dict`).
    """

    def __init__(self, path: Path, example: Path = EXAMPLE, poll_s: float = 2.0,
                 parse: Callable[[dict], T] = config_from_dict) -> None:  # type: ignore[assignment]
        self.path = path
        self.example = example
        self.poll_s = poll_s
        self.parse = parse
        self._mtime = 0.0

    def load(self) -> T:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(self.example, self.path)
        self._mtime = self.path.stat().st_mtime
        return self.parse(json.loads(self.path.read_text()))

    def update(self, changes: dict[str, Any]) -> T:
        """Set top-level keys in the file (rewrites it as indented JSON) and return the parsed result."""
        self.load()
        raw = json.loads(self.path.read_text())
        raw.update(changes)
        self.path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n")
        return self.load()

    async def watch(self, on_change: Callable[[T], None],
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
            except (ValueError, KeyError, TypeError, OSError) as e:
                if on_error:
                    on_error(e)
                continue
            on_change(cfg)
