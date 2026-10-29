"""Composition root: build the adapters, wire the Daemon, run the event loop."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from . import features
from .adapters.claude_cli import ClaudeCliClassifier, JsonFileCache
from .adapters.clock import SystemClock
from .adapters.control_socket import UnixSocketControl
from .adapters.dbus_notifications import BusctlNotificationObserver, BusctlNotificationSink
from .adapters.file_state import AtomicJsonStatePublisher
from .adapters.hyprland import HyprlandWindowSource
from .adapters.json_config import JsonConfigLoader
from .adapters.shell_commands import SubprocessCommandRunner
from .core.daemon import Daemon
from .paths import CACHE_FILE, EVENTS_LOG, MODES_FILE, SOCKET_FILE, STATE_FILE, ensure_dirs


async def run() -> None:
    ensure_dirs()
    config = JsonConfigLoader(MODES_FILE)
    classifier = ClaudeCliClassifier(JsonFileCache(CACHE_FILE))
    windows = HyprlandWindowSource()
    observer = BusctlNotificationObserver()
    daemon = Daemon(config_source=config, classifier=classifier, sink=BusctlNotificationSink(),
                    publisher=AtomicJsonStatePublisher(STATE_FILE), runner=SubprocessCommandRunner(),
                    clock=SystemClock(), events_path=EVENTS_LOG)
    classifier.model = daemon.cfg.llm_model
    daemon.config_listeners.append(lambda cfg: setattr(classifier, "model", cfg.llm_model))
    extra: list[Awaitable[None]] = features.install_all(daemon)
    daemon.start(windows.current())
    control = UnixSocketControl(SOCKET_FILE, daemon)
    await asyncio.gather(
        windows.watch(daemon.on_focus),
        observer.watch(daemon.gate.on_notify, daemon.gate.on_reply),
        config.watch(daemon.apply_config, daemon.on_config_error),
        control.serve(),
        *extra,
    )


def main() -> None:
    asyncio.run(run())
