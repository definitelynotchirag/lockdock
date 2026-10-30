"""Held-notification time limit and do not disturb: the once-a-second expire loop and the
`held_timeout <minutes>` / `dnd on|off|toggle` verbs, both persisted to modes.json (top-level
`notifications.release_after_min` and `dnd`). Logic in core/notifications.py (NotificationGate)."""
from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.daemon import Daemon

TICK_S = 1.0
CONFIG_ERRORS = (ValueError, KeyError, TypeError, OSError)


async def _expire_loop(daemon: Daemon) -> None:
    """Re-deliver notifications held past `notifications.release_after_min`."""
    while True:
        await daemon.clock.sleep(TICK_S)
        daemon.gate.expire(daemon.clock.now())


def held_timeout(daemon: Daemon, arg: Any) -> str:
    """`held_timeout <minutes>`: 0 = never; no argument prints the current limit."""
    current = daemon.cfg.notifications.release_after_min
    if arg in (None, "", []):
        return f"held notifications are released after {current} min" if current else "held notifications wait"
    raw = arg[0] if isinstance(arg, list) and len(arg) == 1 else arg
    try:
        minutes = int(str(raw))
    except ValueError:
        return "usage: held_timeout <minutes>   (0 = never)"
    if minutes < 0:
        return "usage: held_timeout <minutes>   (0 = never)"
    try:
        daemon.update_config({"notifications": {**asdict(daemon.cfg.notifications), "release_after_min": minutes}})
    except CONFIG_ERRORS as e:
        return daemon.on_config_error(e)
    daemon.events.log("held_timeout", minutes=minutes)
    return f"held notifications are released after {minutes} min" if minutes else "held notifications wait"


def dnd(daemon: Daemon, arg: Any) -> str:
    """`dnd on|off|toggle` (no argument: the current state)."""
    word = (arg[0] if isinstance(arg, list) and arg else arg) or "status"
    if word not in ("on", "off", "toggle", "status"):
        return "usage: dnd [on|off|toggle]"
    on = daemon.cfg.dnd
    if word != "status":
        on = (not on) if word == "toggle" else word == "on"
        before = len(daemon.gate.held)
        try:
            daemon.update_config({"dnd": on})
        except CONFIG_ERRORS as e:
            return daemon.on_config_error(e)
        released = before - len(daemon.gate.held)
        if not on and released:
            return f"do not disturb off (released {released})"
    return "do not disturb " + ("on" if on else "off")


def install(daemon: Daemon) -> list[Awaitable[None]]:
    """Register `held_timeout` and `dnd`; return the expire loop."""
    daemon.register_command("held_timeout", lambda arg: held_timeout(daemon, arg))
    daemon.register_command("dnd", lambda arg: dnd(daemon, arg))
    return [_expire_loop(daemon)]
