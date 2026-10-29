"""The desktop's palette: a Material You colors.json (end-4 / matugen) and the gsettings colour scheme."""
from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any


class GsettingsSchemeProbe:
    """Dark or light from `org.gnome.desktop.interface color-scheme`; dark if gsettings is unavailable."""

    def __init__(self, timeout_s: float = 2.0) -> None:
        self.timeout_s = timeout_s

    def prefers_dark(self) -> bool:
        try:
            out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                                 capture_output=True, text=True, timeout=self.timeout_s).stdout
        except (OSError, subprocess.SubprocessError):
            return True
        return "prefer-light" not in out  # prefer-dark, default, or no answer -> dark


class MatugenPaletteSource:
    """PaletteSource over the first existing file in `candidates` (a flat {role: "#rrggbb"} dict).

    `watch` polls the file's mtime (and which candidate exists) every `poll_s`, and the colour
    scheme every `scheme_every` polls, calling on_change after any change.
    """

    def __init__(self, candidates: list[Path], probe: Any = None, poll_s: float = 2.0,
                 scheme_every: int = 3) -> None:
        self.candidates = candidates
        self.probe = probe if probe is not None else GsettingsSchemeProbe()
        self.poll_s = poll_s
        self.scheme_every = scheme_every
        self._dark: bool | None = None

    def path(self) -> Path | None:
        return next((p for p in self.candidates if p.is_file()), None)

    def material(self) -> tuple[dict[str, Any], str] | None:
        p = self.path()
        if p is None:
            return None
        try:
            raw = json.loads(p.read_text())
        except (OSError, ValueError):
            return None
        return (raw, str(p)) if isinstance(raw, dict) else None

    def prefers_dark(self) -> bool:
        if self._dark is None:
            self._dark = self.probe.prefers_dark()
        return self._dark

    def _stamp(self) -> tuple[str, float]:
        p = self.path()
        try:
            return (str(p), p.stat().st_mtime) if p else ("", 0.0)
        except OSError:
            return ("", 0.0)

    async def watch(self, on_change: Callable[[], None]) -> None:
        stamp = self._stamp()
        tick = 0
        while True:
            await asyncio.sleep(self.poll_s)
            tick += 1
            changed = False
            if (new := self._stamp()) != stamp:
                stamp, changed = new, True
            if tick % self.scheme_every == 0:
                dark = await asyncio.to_thread(self.probe.prefers_dark)
                if dark != self._dark:
                    self._dark, changed = dark, True
            if changed:
                on_change()
