"""The Daemon: a thin orchestrator over ModeManager, ActivityJudge and NotificationGate."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .activity import ActivityJudge
from .events import EventLog, EventSink
from .models import Config, Mode, WindowInfo
from .modes import ModeManager
from .notifications import NotificationGate
from .ports import Classifier, Clock, CommandRunner, ConfigSource, NotificationSink, StatePublisher
from .state import SectionProvider, StateSnapshot
from .tasks import Spawn, spawn_task

CommandFn = Callable[[Any], Any]


class Daemon:
    """Owns the core services, publishes a snapshot whenever one of them changes,
    and dispatches control commands. Implements the CommandHandler port.

    Extension points for features: `register_section` (state.json data),
    `register_command` (control socket verbs), `config_listeners` (reload hooks).
    """

    def __init__(self, *, config_source: ConfigSource, classifier: Classifier, sink: NotificationSink,
                 publisher: StatePublisher, runner: CommandRunner, clock: Clock,
                 events_path: Path | None = None, spawn: Spawn = spawn_task) -> None:
        self.config_source = config_source
        self.cfg: Config = config_source.load()
        self.sink = sink
        self.publisher = publisher
        self.clock = clock
        self.events: EventSink = (EventLog(events_path, clock, lambda: self.modes.mode) if events_path
                                  else _NullEvents())
        self.snapshot_builder = StateSnapshot()
        self.config_listeners: list[Callable[[Config], None]] = []
        self.modes = ModeManager(lambda: self.cfg, clock, runner, self.events, self._on_switch,
                                 self.publish, spawn)
        self.judge = ActivityJudge(lambda: self.cfg, lambda: self.modes.cur, classifier, clock, self.events,
                                   self.publish, self._nudge_by_notification, spawn)
        self.gate = NotificationGate(lambda: self.modes.cur, classifier, sink, self.events, self.publish, spawn)
        self._commands: dict[str, CommandFn] = {
            "mode": lambda arg: self.modes.request(arg),
            "cancel": lambda _: (self.modes.cancel(), "cancelled")[1],
            "release": lambda _: f"released {self.gate.release('on request')}",
            "reload": lambda _: self.reload(),
            "status": lambda _: self.snapshot(),
            "reclassify": lambda _: (self.judge.schedule(), "scheduled")[1],
        }

    # ---------- lifecycle ----------
    def start(self, focus: WindowInfo) -> None:
        """Publish the first snapshot and judge the window focused at startup."""
        self.judge.focus = focus
        self.publish()
        self.judge.schedule()

    def on_focus(self, window: WindowInfo) -> None:
        self.judge.on_focus(window)

    # ---------- state ----------
    def register_section(self, name: str, provider: SectionProvider) -> None:
        """Add a top-level state.json section (e.g. "agents", "pet", "theme")."""
        self.snapshot_builder.register_section(name, provider)

    def snapshot(self) -> dict:
        return self.snapshot_builder.build(cfg=self.cfg, mode=self.modes.mode, pending=self.modes.pending,
                                           activity=self.judge.activity, held=self.gate.held,
                                           now=self.clock.now())

    def publish(self) -> None:
        self.publisher.publish(self.snapshot())

    # ---------- config ----------
    def apply_config(self, cfg: Config) -> None:
        """A new modes.json: keep the mode if it still exists, then re-judge."""
        self.cfg = cfg
        self.modes.config_changed()
        for listener in self.config_listeners:
            listener(cfg)
        self.events.log("reload", modes=[m.id for m in cfg.modes])
        self.publish()
        self.judge.schedule()

    def on_config_error(self, e: Exception) -> str:
        self.events.log("config_error", error=str(e))
        return f"modes.json error: {e}"

    def reload(self) -> str:
        try:
            cfg = self.config_source.load()
        except (ValueError, KeyError, OSError) as e:
            return self.on_config_error(e)
        self.apply_config(cfg)
        return "reloaded"

    # ---------- reactions ----------
    def _on_switch(self, old: Mode, new: Mode) -> None:
        self.gate.release(f"while you were in {old.label}")
        self.publish()
        self.judge.schedule()

    def _nudge_by_notification(self, mode: Mode, w: WindowInfo, reason: str) -> None:
        self.sink.send("lockdock", f"Off task in {mode.label}", f"{w.cls}: {w.title}\n{reason}",
                       urgency=1, timeout_ms=4000)

    # ---------- control commands ----------
    def register_command(self, name: str, fn: CommandFn) -> None:
        """Add a control-socket verb; `fn(arg)` returns a JSON-able result."""
        self._commands[name] = fn

    def handle(self, cmd: str | None, arg: Any) -> Any:
        fn = self._commands.get(cmd or "")
        return fn(arg) if fn else f"unknown command {cmd!r}"


class _NullEvents:
    """Discards events (used when no EventLog is wired)."""

    def log(self, kind: str, **data: Any) -> None:
        pass
