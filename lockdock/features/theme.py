"""Theme feature: theme.json + the desktop palette -> `theme` state section, plus theme_get / theme_set /
theme_reset, and pin (on / off / toggle `pinned`). The palette follows the Material You colors.json (end-4 / matugen) live."""
from __future__ import annotations

from collections.abc import Awaitable
from pathlib import Path
from typing import TYPE_CHECKING

from ..adapters.json_config import JsonFileWatcher
from ..adapters.system_palette import MatugenPaletteSource
from ..core.ports import PaletteSource
from ..core.theme import ThemeService
from ..paths import PALETTE_FILES, THEME_FILE

if TYPE_CHECKING:
    from ..core.daemon import Daemon

EXAMPLE = Path(__file__).resolve().parents[2] / "theme.example.json"


def install(daemon: Daemon, path: Path = THEME_FILE, example: Path = EXAMPLE,
            palette: PaletteSource | None = None) -> list[Awaitable[None]]:
    """Load the theme, publish it, expose the commands, and return the file and palette watchers."""
    doc = JsonFileWatcher(path, example)
    palette = palette if palette is not None else MatugenPaletteSource(PALETTE_FILES)
    service = ThemeService(doc, daemon.publish, daemon.events.log, palette)
    service.load()
    daemon.register_section("theme", service.snapshot)
    daemon.register_command("theme_get", service.get)
    daemon.register_command("theme_set", service.set)
    daemon.register_command("theme_reset", service.reset)
    daemon.register_command("pin", service.pin)
    return [doc.watch(service.apply, service.on_file_error), palette.watch(service.refresh_palette)]
