"""Theme feature: theme.json -> `theme` state section, plus theme_get / theme_set / theme_reset."""
from __future__ import annotations

from collections.abc import Awaitable
from pathlib import Path
from typing import TYPE_CHECKING

from ..adapters.json_config import JsonFileWatcher
from ..core.theme import ThemeService
from ..paths import THEME_FILE

if TYPE_CHECKING:
    from ..core.daemon import Daemon

EXAMPLE = Path(__file__).resolve().parents[2] / "theme.example.json"


def install(daemon: Daemon, path: Path = THEME_FILE, example: Path = EXAMPLE) -> list[Awaitable[None]]:
    """Load the theme, publish it, expose the commands, and return the file watcher."""
    doc = JsonFileWatcher(path, example)
    service = ThemeService(doc, daemon.publish, daemon.events.log)
    service.load()
    daemon.register_section("theme", service.snapshot)
    daemon.register_command("theme_get", service.get)
    daemon.register_command("theme_set", service.set)
    daemon.register_command("theme_reset", service.reset)
    return [doc.watch(service.apply, service.on_file_error)]
