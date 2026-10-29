"""Mode config: ~/.config/lockdock/modes.json.

This file is the agent surface. An agent (Claude Code, etc.) edits it to add a
mode or change what a mode allows; the daemon hot-reloads it on change.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .paths import MODES_FILE

DEFAULT_BROWSERS = ["helium", "chrom", "firefox", "zen", "brave", "vivaldi", "librewolf", "edge", "opera"]
EXAMPLE = Path(__file__).resolve().parent.parent / "modes.example.json"


@dataclass
class Notifications:
    allow_from: list[str] = field(default_factory=list)   # app names / desktop ids always shown
    hold_from: list[str] = field(default_factory=list)    # always held
    pass_keywords: list[str] = field(default_factory=list)  # summary/body match -> shown
    default: str = "hold"   # hold | pass | ask  (ask = LLM decides)


@dataclass
class Mode:
    id: str
    label: str
    icon: str = "●"
    color: str = "#f0a04b"
    description: str = ""
    apps: list[str] = field(default_factory=list)        # desktop ids shown in the dock
    on_task: list[str] = field(default_factory=list)     # regex on "class|title" -> on task
    off_task: list[str] = field(default_factory=list)    # regex on "class|title" -> off task
    unknown: str = "ask"                                  # ask | neutral | off
    off_task_action: str = "nudge"                        # nudge | notify | none
    notifications: Notifications = field(default_factory=Notifications)
    exit_delay_s: int = 0
    per_press_s: int = 0
    on_enter: list[str] = field(default_factory=list)    # shell commands
    on_exit: list[str] = field(default_factory=list)

    def matches(self, patterns: list[str], text: str) -> str | None:
        for p in patterns:
            try:
                if re.search(p, text, re.I):
                    return p
            except re.error:
                if p.lower() in text.lower():
                    return p
        return None


@dataclass
class Config:
    modes: list[Mode]
    default_mode: str
    llm_enabled: bool = True
    llm_model: str = "haiku"
    dwell_s: float = 2.0
    browsers: list[str] = field(default_factory=lambda: DEFAULT_BROWSERS)

    def get(self, mode_id: str) -> Mode | None:
        return next((m for m in self.modes if m.id == mode_id), None)


def load() -> Config:
    if not MODES_FILE.exists():
        MODES_FILE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(EXAMPLE, MODES_FILE)
    raw = json.loads(MODES_FILE.read_text())
    modes = []
    for m in raw["modes"]:
        n = m.get("notifications", {})
        modes.append(Mode(
            id=m["id"], label=m.get("label", m["id"].title()), icon=m.get("icon", "●"),
            color=m.get("color", "#f0a04b"), description=m.get("description", ""),
            apps=m.get("apps", []), on_task=m.get("on_task", []), off_task=m.get("off_task", []),
            unknown=m.get("unknown", "ask"), off_task_action=m.get("off_task_action", "nudge"),
            notifications=Notifications(
                allow_from=n.get("allow_from", []), hold_from=n.get("hold_from", []),
                pass_keywords=n.get("pass_keywords", []), default=n.get("default", "hold")),
            exit_delay_s=int(m.get("exit_delay_s", 0)), per_press_s=int(m.get("per_press_s", 0)),
            on_enter=m.get("on_enter", []), on_exit=m.get("on_exit", []),
        ))
    llm = raw.get("llm", {})
    return Config(modes=modes, default_mode=raw.get("default_mode", modes[0].id),
                  llm_enabled=llm.get("enabled", True), llm_model=llm.get("model", "haiku"),
                  dwell_s=float(raw.get("dwell_s", 2.0)),
                  browsers=raw.get("browsers", DEFAULT_BROWSERS))
