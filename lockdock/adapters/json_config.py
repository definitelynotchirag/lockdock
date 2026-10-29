"""User-edited JSON files (modes.json, pet.json, theme.json): seed from an example, parse, hot-reload."""
from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, Generic, TypeVar

from ..core.agents import DEFAULT_KINDS, merge_kinds
from ..core.models import DEFAULT_BROWSERS, BrowserBridge, Config, Mode, NotificationRules

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
    bb = raw.get("browser_bridge", {})
    bridge = BrowserBridge(enabled=bool(bb.get("enabled", True)), port=int(bb.get("port", 47231)),
                           token=str(bb.get("token", "")))
    return Config(modes=modes, default_mode=raw.get("default_mode", modes[0].id),
                  llm_enabled=llm.get("enabled", True), llm_model=llm.get("model", "haiku"),
                  dwell_s=float(raw.get("dwell_s", 2.0)),
                  browsers=raw.get("browsers", list(DEFAULT_BROWSERS)), browser_bridge=bridge,
                  agent_kinds=(merge_kinds(DEFAULT_KINDS, raw["agents"].get("kinds", []))
                               if isinstance(raw.get("agents"), dict) else None))


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


class JsonConfigLoader(Generic[T]):
    """ConfigSource for a JSON file, parsed into a typed config.

    Defaults to ~/.config/lockdock/modes.json -> Config; pass `parse` for another
    file (pet.json uses `pet_config_from_dict`). Built on JsonFileWatcher.
    """

    def __init__(self, path: Path, example: Path = EXAMPLE, poll_s: float = 2.0,
                 parse: Callable[[dict], T] = config_from_dict) -> None:  # type: ignore[assignment]
        self.file = JsonFileWatcher(path, example, poll_s)
        self.path = path
        self.parse = parse

    def load(self) -> T:
        return self.parse(self.file.read())

    def update(self, changes: dict[str, Any]) -> T:
        """Set top-level keys in the file (rewrites it as indented JSON) and return the parsed result."""
        raw = self.file.read()
        raw.update(changes)
        self.file.write(raw)
        return self.load()

    async def watch(self, on_change: Callable[[T], None],
                    on_error: Callable[[Exception], None] | None = None) -> None:
        """On an edit, parse and hand the new config to on_change; bad edits go to on_error."""
        def changed(raw: Any) -> None:
            try:
                cfg = self.parse(raw)
            except (ValueError, KeyError, TypeError) as e:
                if on_error:
                    on_error(e)
                return
            on_change(cfg)

        await self.file.watch(changed, on_error)
