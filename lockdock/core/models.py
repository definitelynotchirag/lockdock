"""Domain dataclasses shared by the core services and the adapters."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

DEFAULT_BROWSERS: tuple[str, ...] = (
    "helium", "chrom", "firefox", "zen", "brave", "vivaldi", "librewolf", "edge", "opera")


class Verdict(StrEnum):
    """Whether the focused window fits the current mode."""

    ON = "on"
    OFF = "off"
    NEUTRAL = "neutral"


@dataclass
class NotificationRules:
    """Per-mode notification policy (the `notifications` block in modes.json)."""

    allow_from: list[str] = field(default_factory=list)     # regex on "app|desktop-entry" -> pass
    hold_from: list[str] = field(default_factory=list)      # regex on "app|desktop-entry" -> hold
    pass_keywords: list[str] = field(default_factory=list)  # regex on summary+body -> pass
    default: str = "hold"                                   # hold | pass | ask (ask = classifier decides)


@dataclass
class Mode:
    """One focus mode from modes.json."""

    id: str
    label: str
    icon: str = "●"
    color: str = "#f0a04b"
    description: str = ""
    apps: list[str] = field(default_factory=list)       # desktop ids shown in the dock
    on_task: list[str] = field(default_factory=list)    # regex on "class|title" -> on task
    off_task: list[str] = field(default_factory=list)   # regex on "class|title" -> off task
    unknown: str = "ask"                                # ask | neutral | off
    off_task_action: str = "nudge"                      # nudge | notify | none
    notifications: NotificationRules = field(default_factory=NotificationRules)
    exit_delay_s: int = 0
    per_press_s: int = 0
    on_enter: list[str] = field(default_factory=list)   # shell commands
    on_exit: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentKind:
    """One row of the agent detection table (see core.agents.DEFAULT_KINDS).

    `patterns` are case-insensitive regexes full-matched against a process's
    program names (basename of argv[0], or of the script an interpreter runs);
    a pattern containing "/" is searched in the full path instead. `ancestors`
    (optional) must match some ancestor's program name; `exclude` full-matches
    single arguments that disqualify the process (e.g. `-p`). `label_arg` names
    a flag whose value's basename becomes the label. `hook_kind` is the kind
    hook events for it arrive as (default: `name`).
    """

    name: str
    glyph: str = "◆"
    patterns: tuple[str, ...] = ()
    ancestors: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    label_arg: str = ""
    hook_kind: str = ""

    @property
    def event_kind(self) -> str:
        return self.hook_kind or self.name


class AgentState(StrEnum):
    """What a coding agent is doing, as far as lockdock can tell."""

    WORKING = "working"
    NEEDS_INPUT = "needs_input"
    DONE = "done"
    IDLE = "idle"


@dataclass
class AgentInfo:
    """One running (or recently finished) coding agent, as published in state.json `agents`."""

    id: str
    kind: str
    label: str
    state: AgentState = AgentState.IDLE
    since_ms: int = 0
    pid: int | None = None
    cwd: str = ""
    window_address: str | None = None
    last_message: str = ""
    session_id: str = ""
    glyph: str = "◆"

    def to_dict(self) -> dict:
        """The form published in state.json."""
        return {"id": self.id, "kind": self.kind, "label": self.label, "state": str(self.state),
                "since_ms": self.since_ms, "pid": self.pid, "cwd": self.cwd,
                "window_address": self.window_address, "last_message": self.last_message,
                "session_id": self.session_id, "glyph": self.glyph}


@dataclass(frozen=True)
class ProcessInfo:
    """One process from a ProcessScanner. `cpu_s` is total user+system CPU seconds."""

    pid: int
    ppid: int
    cmdline: tuple[str, ...]
    cwd: str = ""
    cpu_s: float = 0.0


@dataclass
class Config:
    """The whole modes.json, parsed."""

    modes: list[Mode]
    default_mode: str
    llm_enabled: bool = True
    llm_model: str = "haiku"
    dwell_s: float = 2.0
    browsers: list[str] = field(default_factory=lambda: list(DEFAULT_BROWSERS))
    agent_kinds: list[AgentKind] | None = None   # None = the built-in table (core.agents.DEFAULT_KINDS)

    def get(self, mode_id: str | None) -> Mode | None:
        """The mode with this id, or None."""
        return next((m for m in self.modes if m.id == mode_id), None)


ModeConfig = Config


@dataclass(frozen=True)
class WindowInfo:
    """The focused window as the core sees it. `url` is filled by a UrlSource for browsers."""

    cls: str = ""
    title: str = ""
    url: str | None = None
    pid: int | None = None
    address: str | None = None   # compositor window address ("0x..."), when the source knows it

    def key(self) -> tuple[str, str, str | None]:
        """Identity used to detect that focus moved on while a verdict was being computed."""
        return (self.cls, self.title, self.url)


@dataclass
class Notification:
    """One org.freedesktop.Notifications Notify call observed on the bus."""

    app: str
    summary: str
    body: str
    urgency: int = 1
    desktop_entry: str = ""
    id: int | None = None
    ts: float = 0.0
    sender: str = ""
    cookie: int = 0
    hints: dict = field(default_factory=dict)

    def short(self) -> dict:
        """The form published in state.json."""
        return {"app": self.app, "summary": self.summary, "body": self.body[:200],
                "urgency": self.urgency, "ts": self.ts, "id": self.id}


@dataclass(frozen=True)
class NotificationDecision:
    """What to do with a notification: `pass`, `hold`, or `ask` (the classifier decides)."""

    action: str
    reason: str = ""


@dataclass
class PendingSwitch:
    """A mode switch waiting for its exit countdown."""

    mode: str
    deadline: float
    total: float
