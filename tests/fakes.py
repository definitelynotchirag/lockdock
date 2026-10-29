"""Stdlib-only fakes for every port in lockdock.core.ports."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from lockdock.core.models import (Config, Mode, Notification, NotificationRules, ProcessInfo, Verdict,
                                  WindowInfo)


class FakeClock:
    """Manual time; sleep() just yields."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def now(self) -> float:
        return self.t

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(0)


class FakeWindowSource:
    def __init__(self, window: WindowInfo = WindowInfo()) -> None:
        self.window = window

    def current(self) -> WindowInfo:
        return self.window

    async def watch(self, on_focus: Callable[[WindowInfo], None]) -> None:
        on_focus(self.window)


class FakeUrlSource:
    def __init__(self, events: list[tuple[str, str]]) -> None:
        self.events = events

    async def watch(self, on_url: Callable[[str, str], None]) -> None:
        for cls, url in self.events:
            on_url(cls, url)


class FakeNotificationObserver:
    def __init__(self, notes: list[Notification]) -> None:
        self.notes = notes

    async def watch(self, on_notify: Callable[[Notification], None],
                    on_reply: Callable[[int, int, str], None]) -> None:
        for i, n in enumerate(self.notes):
            on_notify(n)
            on_reply(n.cookie, 100 + i, n.sender)


class FakeSink:
    def __init__(self) -> None:
        self.closed: list[int] = []
        self.sent: list[dict] = []

    def close(self, id: int) -> None:
        self.closed.append(id)

    def send(self, app: str, summary: str, body: str, desktop_entry: str = "", urgency: int = 1,
             timeout_ms: int = -1) -> None:
        self.sent.append({"app": app, "summary": summary, "body": body, "desktop_entry": desktop_entry,
                          "urgency": urgency, "timeout_ms": timeout_ms})


class FakeClassifier:
    def __init__(self, activity: tuple[Verdict, str] = (Verdict.NEUTRAL, "fake"),
                 notification: tuple[str, str] = ("pass", "fake")) -> None:
        self.activity_result = activity
        self.notification_result = notification
        self.calls: list[tuple[str, Any]] = []

    async def activity(self, mode: Mode, window: WindowInfo) -> tuple[Verdict, str]:
        self.calls.append(("activity", window))
        return self.activity_result

    async def notification(self, mode: Mode, n: Notification) -> tuple[str, str]:
        self.calls.append(("notification", n))
        return self.notification_result


class FakePublisher:
    def __init__(self) -> None:
        self.snapshots: list[dict] = []

    def publish(self, snapshot: dict) -> None:
        self.snapshots.append(snapshot)


class FakeRunner:
    def __init__(self) -> None:
        self.cmds: list[str] = []

    def run(self, cmd: str) -> None:
        self.cmds.append(cmd)


class FakeConfigSource:
    def __init__(self, cfg: Config, error: Exception | None = None) -> None:
        self.cfg = cfg
        self.error = error

    def load(self) -> Config:
        if self.error:
            raise self.error
        return self.cfg

    async def watch(self, on_change: Callable[[Config], None],
                    on_error: Callable[[Exception], None] | None = None) -> None:
        on_change(self.cfg)


class FakeEvents:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def log(self, kind: str, **data: Any) -> None:
        self.records.append({"kind": kind, **data})

    def kinds(self) -> list[str]:
        return [r["kind"] for r in self.records]


class FakeProcessScanner:
    """Returns whatever process list the test sets."""

    def __init__(self, procs: list[ProcessInfo] | None = None) -> None:
        self.procs = procs or []

    def scan(self) -> list[ProcessInfo]:
        return list(self.procs)


class Spawner:
    """Collects spawned coroutines instead of scheduling them."""

    def __init__(self) -> None:
        self.coros: list[Coroutine[Any, Any, None]] = []

    def __call__(self, coro: Coroutine[Any, Any, None]) -> None:
        self.coros.append(coro)
        return None

    def drain(self) -> None:
        """Run every collected coroutine to completion (newest first, like a cancelled-and-replaced task)."""
        while self.coros:
            asyncio.run(self.coros.pop(0))

    def discard(self) -> None:
        for c in self.coros:
            c.close()
        self.coros.clear()


def make_config(**overrides: Any) -> Config:
    """Free / writing / building modes, close to modes.example.json."""
    free = Mode(id="free", label="Free", on_task=[".*"], unknown="neutral",
                notifications=NotificationRules(default="pass"))
    writing = Mode(id="writing", label="Writing", apps=["md.obsidian.Obsidian", "helium"],
                   on_task=["obsidian", r"docs\.google", "wikipedia"],
                   off_task=["youtube", "reddit", "slack"], unknown="ask",
                   notifications=NotificationRules(allow_from=["Calendar"], hold_from=["Discord"],
                                                   pass_keywords=["urgent"], default="hold"),
                   exit_delay_s=30, per_press_s=10, on_enter=["echo enter-writing"],
                   on_exit=["echo exit-writing"])
    building = Mode(id="building", label="Building", apps=["dev.zed.Zed", "kitty", "helium"],
                    on_task=["zed", "github"], off_task=["youtube"], unknown="ask",
                    notifications=NotificationRules(allow_from=["GitHub"], default="ask"),
                    exit_delay_s=20, per_press_s=0, on_enter=["echo enter-building"])
    kw: dict[str, Any] = {"modes": [free, writing, building], "default_mode": "free", "dwell_s": 0.0,
                          "browsers": ["helium", "firefox"]}
    kw.update(overrides)
    return Config(**kw)


class FakeSpeaker:
    """Speaker that answers with a fixed line and records the calls."""

    def __init__(self, text: str | None = "llm line") -> None:
        self.text = text
        self.calls: list[tuple[str, str, str, str, str]] = []

    async def line(self, mood: str, mode: str, app: str, title: str, reason: str) -> str | None:
        self.calls.append((mood, mode, app, title, reason))
        return self.text


class FakePetPacks:
    """PetPackSource over an in-memory {name: manifest} dict."""

    def __init__(self, packs: dict[str, dict] | None = None) -> None:
        self.packs = packs if packs is not None else {"cat": {"name": "Miso", "size": 48, "moods": {}}}

    def resolve(self, name: str) -> tuple[str, dict] | None:
        return (f"/packs/{name}", self.packs[name]) if name in self.packs else None

    def available(self) -> list[dict]:
        return [{"name": n, "title": m.get("name", n), "author": "", "source": "fake", "dir": f"/packs/{n}"}
                for n, m in self.packs.items()]
