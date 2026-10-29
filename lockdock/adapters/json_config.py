"""modes.json: parse into core Config, hot-reload on mtime change."""
from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

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
                  browsers=raw.get("browsers", list(DEFAULT_BROWSERS)))


class JsonFileWatcher:
    """JsonDocument for a user-edited JSON file: seeded from an example, polled by mtime.

    `read()` creates the file from `example` when missing; `write()` is atomic and does not
    count as an external edit; `watch()` hands every externally edited, parsed file to on_change.
    """

    def __init__(self, path: Path, example: Path, poll_s: float = 2.0) -> None:
        self.path = path
        self.example = example
        self.poll_s = poll_s
        self._mtime = 0.0

    def read(self) -> Any:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(self.example, self.path)
        self._mtime = self.path.stat().st_mtime
        return json.loads(self.path.read_text())

    def write(self, raw: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n")
        tmp.replace(self.path)
        self._mtime = self.path.stat().st_mtime

    async def watch(self, on_change: Callable[[Any], None],
                    on_error: Callable[[Exception], None] | None = None) -> None:
        """Poll the mtime; on a change, parse the file and hand it to on_change."""
        while True:
            await asyncio.sleep(self.poll_s)
            try:
                mt = self.path.stat().st_mtime
            except OSError:
                continue
            if mt == self._mtime:
                continue
            try:
                raw = self.read()
            except (ValueError, OSError) as e:
                self._mtime = mt
                if on_error:
                    on_error(e)
                continue
            on_change(raw)


class JsonConfigLoader:
    """ConfigSource for ~/.config/lockdock/modes.json (seeded from modes.example.json)."""

    def __init__(self, path: Path, example: Path = EXAMPLE, poll_s: float = 2.0) -> None:
        self.file = JsonFileWatcher(path, example, poll_s)
        self.path = path

    def load(self) -> Config:
        return config_from_dict(self.file.read())

    async def watch(self, on_change: Callable[[Config], None],
                    on_error: Callable[[Exception], None] | None = None) -> None:
        """On an edit, parse into a Config and hand it to on_change; bad edits go to on_error."""
        def changed(raw: Any) -> None:
            try:
                cfg = config_from_dict(raw)
            except (ValueError, KeyError) as e:
                if on_error:
                    on_error(e)
                return
            on_change(cfg)

        await self.file.watch(changed, on_error)
