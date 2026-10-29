"""Composition root: build the adapters, wire the Daemon, run the event loop."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping
from pathlib import Path

from . import features
from .adapters.claude_cli import ClaudeCliClassifier, JsonFileCache
from .adapters.clock import SystemClock
from .adapters.control_socket import UnixSocketControl
from .adapters.dbus_notifications import BusctlNotificationObserver, BusctlNotificationSink
from .adapters.file_state import AtomicJsonStatePublisher
from .adapters.env_file import lookup
from .adapters.hyprland import HyprlandWindowSource
from .adapters.jev import JevClassifier
from .adapters.json_config import JsonConfigLoader
from .adapters.shell_commands import SubprocessCommandRunner
from .core.daemon import Daemon
from .core.models import Config
from .paths import CACHE_FILE, ENV_FILE, EVENTS_LOG, MODES_FILE, SOCKET_FILE, STATE_FILE, ensure_dirs

JEV_KEY = "TYPESAFE_API_KEY"


def pick_classifier(cfg: Config, cache: JsonFileCache, environ: Mapping[str, str] | None = None,
                    env_file: Path = ENV_FILE) -> tuple[ClaudeCliClassifier | JevClassifier, str | None]:
    """The classifier for `llm.provider` (read once, at startup), and an error to log when the
    choice could not be honoured. The Jev key comes from the environment, then the .env file."""
    if cfg.llm_provider == "jev":
        key = lookup(JEV_KEY, env_file, environ)
        if key:
            return JevClassifier(cache, key, cfg.jev_model, cfg.min_confidence), None
        return ClaudeCliClassifier(cache, cfg.llm_model), f"{JEV_KEY} missing, falling back to claude"
    return ClaudeCliClassifier(cache, cfg.llm_model), None


def sync_classifier(classifier: ClaudeCliClassifier | JevClassifier, cfg: Config) -> str | None:
    """Apply a reloaded modes.json to the running classifier; a note when the provider changed
    (switching providers needs a daemon restart)."""
    if isinstance(classifier, JevClassifier):
        classifier.model, classifier.min_confidence = cfg.jev_model, cfg.min_confidence
    else:
        classifier.model = cfg.llm_model
    if cfg.llm_provider != classifier.provider:
        return f"llm.provider is {cfg.llm_provider!r} but {classifier.provider!r} is running; restart the daemon"
    return None


async def run() -> None:
    ensure_dirs()
    config = JsonConfigLoader(MODES_FILE)
    classifier, problem = pick_classifier(config.load(), JsonFileCache(CACHE_FILE))
    windows = HyprlandWindowSource()
    observer = BusctlNotificationObserver()
    daemon = Daemon(config_source=config, classifier=classifier, sink=BusctlNotificationSink(),
                    publisher=AtomicJsonStatePublisher(STATE_FILE), runner=SubprocessCommandRunner(),
                    clock=SystemClock(), events_path=EVENTS_LOG)
    if problem:
        daemon.events.log("config_error", error=problem)
    if isinstance(classifier, JevClassifier):
        classifier.on_usage = lambda rec: daemon.events.log("classifier", **rec)
    sync_classifier(classifier, daemon.cfg)

    def on_config(cfg: Config) -> None:
        if note := sync_classifier(classifier, cfg):
            daemon.events.log("config_error", error=note)

    daemon.config_listeners.append(on_config)
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
