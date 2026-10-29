"""Interfaces between the core and the outside world. Adapters implement these."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from .models import Config, Mode, Notification, ProcessInfo, Verdict, WindowInfo


class WindowSource(Protocol):
    """Reports which window has focus."""

    async def watch(self, on_focus: Callable[[WindowInfo], None]) -> None: ...
    def current(self) -> WindowInfo: ...


class UrlSource(Protocol):
    """Reports the URL of the active browser tab (e.g. from a browser extension)."""

    async def watch(self, on_url: Callable[[str, str], None]) -> None: ...  # (browser_class, url)


class NotificationObserver(Protocol):
    """Observes Notify calls and the id replies the notification daemon sends back."""

    async def watch(self, on_notify: Callable[[Notification], None],
                    on_reply: Callable[[int, int, str], None]) -> None: ...  # on_reply(cookie, id, sender)


class NotificationSink(Protocol):
    """Closes and (re)sends desktop notifications."""

    def close(self, id: int) -> None: ...
    def send(self, app: str, summary: str, body: str, desktop_entry: str = "", urgency: int = 1,
             timeout_ms: int = -1) -> None: ...


class Classifier(Protocol):
    """Judges what the rules could not decide."""

    async def activity(self, mode: Mode, window: WindowInfo) -> tuple[Verdict, str]: ...
    async def notification(self, mode: Mode, n: Notification) -> tuple[str, str]: ...


class StatePublisher(Protocol):
    """Makes the state snapshot visible to the dock."""

    def publish(self, snapshot: dict) -> None: ...


class CommandRunner(Protocol):
    """Runs on_enter / on_exit shell commands."""

    def run(self, cmd: str) -> None: ...


class ConfigSource(Protocol):
    """Loads modes config and reports edits."""

    def load(self) -> Config: ...
    async def watch(self, on_change: Callable[[Config], None],
                    on_error: Callable[[Exception], None] | None = None) -> None: ...


class CommandHandler(Protocol):
    """Handles one control command (from the unix socket or elsewhere)."""

    def handle(self, cmd: str | None, arg: Any) -> Any: ...


class Clock(Protocol):
    """Wall time and sleeping; faked in tests."""

    def now(self) -> float: ...
    async def sleep(self, seconds: float) -> None: ...


class ProcessScanner(Protocol):
    """Lists the user's processes (pid, ppid, argv, cwd, cpu time)."""

    def scan(self) -> list[ProcessInfo]: ...


class Speaker(Protocol):
    """Writes one short in-character line for the pet (e.g. an LLM); None means "use a template"."""

    async def line(self, mood: str, mode: str, app: str, title: str, reason: str) -> str | None: ...


class PetPackSource(Protocol):
    """Finds sprite packs by name (user packs shadow built-in ones)."""

    def resolve(self, name: str) -> tuple[str, dict] | None: ...  # (pack_dir, pack.json manifest)
    def available(self) -> list[dict]: ...                        # [{name, title, author, source, dir}]
