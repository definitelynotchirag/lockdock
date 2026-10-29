"""Agent inbox: one dock chip per running coding agent, red when it waits for the user.

Wires a /proc ProcessScanner (every 3 s) and agent hook events into an
AgentRegistry, publishes it as the `agents` state section and adds the control
commands `agent_event`, `agent_focus` and `agents`.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from ..adapters import hyprland
from ..adapters.proc_scan import ProcScanner
from ..core.agents import DEFAULT_KINDS, AgentRegistry, parse_hook_event
from ..core.models import Config
from ..core.ports import Clock, ProcessScanner

if TYPE_CHECKING:
    from ..core.daemon import Daemon

SCAN_INTERVAL_S = 3.0


class WindowIndex:
    """pid -> window address, fetched lazily at most once per scan."""

    def __init__(self, fetch: Callable[[], dict[int, str]] = hyprland.window_index) -> None:
        self.fetch = fetch
        self._index: dict[int, str] | None = None

    def invalidate(self) -> None:
        self._index = None

    def __call__(self, pid: int) -> str | None:
        if self._index is None:
            self._index = self.fetch()
        return self._index.get(pid)


def _kinds(cfg: Config) -> list:
    return list(DEFAULT_KINDS) if cfg.agent_kinds is None else cfg.agent_kinds


def make_commands(registry: AgentRegistry, focus_window: Callable[[str], None]) -> dict[str, Callable[[Any], Any]]:
    """The control-socket verbs of this feature."""

    def agent_event(arg: Any) -> Any:
        if not isinstance(arg, dict):
            return "agent_event needs {kind, state, payload, pids}"
        try:
            ev = parse_hook_event(str(arg.get("kind", "")), str(arg.get("state", "")), arg.get("payload"),
                                  arg.get("pids") or ())
        except (ValueError, TypeError) as e:
            return f"bad agent event: {e}"
        return registry.on_event(ev).id

    def agent_focus(arg: Any) -> Any:
        a = registry.get(str(arg or ""))
        if a is None:
            return f"no agent {arg!r}"
        if not a.window_address:
            return f"no window for {a.id}"
        focus_window(a.window_address)
        return f"focused {a.id}"

    return {"agent_event": agent_event, "agent_focus": agent_focus, "agents": lambda _: registry.snapshot()}


async def scan_loop(scanner: ProcessScanner, registry: AgentRegistry, windows: WindowIndex, clock: Clock,
                    interval: float = SCAN_INTERVAL_S) -> None:
    """Scan processes forever; a failed scan is skipped, never fatal."""
    while True:
        try:
            procs = await asyncio.to_thread(scanner.scan)
            windows.invalidate()
            registry.on_scan(procs)
        except OSError:
            pass
        await clock.sleep(interval)


def install(daemon: Daemon) -> list[Awaitable[None]]:
    windows = WindowIndex()
    registry = AgentRegistry(daemon.clock, daemon.publish, windows, _kinds(daemon.cfg), daemon.sink,
                             daemon.events)
    daemon.register_section("agents", registry.snapshot)
    for name, fn in make_commands(registry, lambda addr: hyprland.dispatch("focuswindow",
                                                                           f"address:{addr}")).items():
        daemon.register_command(name, fn)
    daemon.config_listeners.append(lambda cfg: setattr(registry, "kinds", _kinds(cfg)))
    daemon.focus_listeners.append(lambda w: registry.on_focus(w.address))
    return [scan_loop(ProcScanner(), registry, windows, daemon.clock)]
