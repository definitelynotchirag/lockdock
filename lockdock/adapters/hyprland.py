"""Hyprland IPC: focus events from .socket2 and hyprctl queries."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from ..core.models import WindowInfo


def _sock(name: str) -> Path:
    base = Path(os.environ["XDG_RUNTIME_DIR"]) / "hypr" / os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
    return base / name


def hyprctl(*args: str) -> str:
    return subprocess.run(["hyprctl", *args], capture_output=True, text=True, check=False).stdout


def _json(*args: str) -> object:
    try:
        return json.loads(hyprctl("-j", *args) or "null")
    except json.JSONDecodeError:
        return None


def clients() -> list[dict]:
    """All Hyprland clients (`hyprctl -j clients`)."""
    data = _json("clients")
    return data if isinstance(data, list) else []


def pid_for_class(cls: str) -> int | None:
    """The pid of the first client whose class matches `cls` (case-insensitive)."""
    for c in clients():
        if str(c.get("class", "")).lower() == cls.lower() and c.get("pid"):
            return int(c["pid"])
    return None


def dispatch(*args: str) -> None:
    subprocess.Popen(["hyprctl", "dispatch", *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class HyprlandWindowSource:
    """WindowSource backed by Hyprland's event socket and `hyprctl activewindow`."""

    def current(self) -> WindowInfo:
        d = _json("activewindow")
        if not isinstance(d, dict):
            return WindowInfo()
        pid = d.get("pid")
        return WindowInfo(cls=d.get("class", ""), title=d.get("title", ""),
                          pid=int(pid) if isinstance(pid, int) and pid > 0 else None)

    async def watch(self, on_focus: Callable[[WindowInfo], None]) -> None:
        """Call on_focus for every activewindow event. Reconnects on error."""
        while True:
            try:
                reader, _ = await asyncio.open_unix_connection(str(_sock(".socket2.sock")))
                while line := await reader.readline():
                    ev, _, data = line.decode(errors="replace").rstrip("\n").partition(">>")
                    if ev == "activewindow":
                        cls, _, title = data.partition(",")
                        on_focus(WindowInfo(cls=cls, title=title))
            except (OSError, asyncio.IncompleteReadError):
                await asyncio.sleep(2)
