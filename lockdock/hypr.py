"""Hyprland IPC: focus events from .socket2 and hyprctl queries."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path


def _sock(name: str) -> Path:
    base = Path(os.environ["XDG_RUNTIME_DIR"]) / "hypr" / os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
    return base / name


def hyprctl(*args: str) -> str:
    return subprocess.run(["hyprctl", *args], capture_output=True, text=True, check=False).stdout


def active_window() -> tuple[str, str]:
    try:
        d = json.loads(hyprctl("-j", "activewindow") or "{}")
        return d.get("class", ""), d.get("title", "")
    except json.JSONDecodeError:
        return "", ""


def dispatch(*args: str) -> None:
    subprocess.Popen(["hyprctl", "dispatch", *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def watch_focus(on_focus: Callable[[str, str], None]) -> None:
    """Call on_focus(class, title) for every activewindow event. Reconnects on error."""
    while True:
        try:
            reader, _ = await asyncio.open_unix_connection(str(_sock(".socket2.sock")))
            while line := await reader.readline():
                ev, _, data = line.decode(errors="replace").rstrip("\n").partition(">>")
                if ev == "activewindow":
                    cls, _, title = data.partition(",")
                    on_focus(cls, title)
        except (OSError, asyncio.IncompleteReadError):
            await asyncio.sleep(2)
