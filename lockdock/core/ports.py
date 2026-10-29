"""Interfaces between the core and the outside world. Adapters implement these."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from .models import Config, Mode, Notification, Verdict, WindowInfo


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


class JsonDocument(Protocol):
    """A JSON file the user or an agent edits: read, write, and report external edits."""

    def read(self) -> Any: ...
    def write(self, raw: Any) -> None: ...
    async def watch(self, on_change: Callable[[Any], None],
                    on_error: Callable[[Exception], None] | None = None) -> None: ...


class CommandHandler(Protocol):
    """Handles one control command (from the unix socket or elsewhere)."""

    def handle(self, cmd: str | None, arg: Any) -> Any: ...


class Clock(Protocol):
    """Wall time and sleeping; faked in tests."""

    def now(self) -> float: ...
    async def sleep(self, seconds: float) -> None: ...
