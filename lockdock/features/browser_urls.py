"""Browser URL bridge: the extension reports the active tab URL, so browser windows are judged
by URL as well as title. Config: top-level `"browser_bridge": {"enabled", "port", "token"}`."""
from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import replace
from typing import TYPE_CHECKING

from ..adapters.http_url_source import HttpUrlSource
from ..core.models import WindowInfo
from ..core.ports import UrlSource

if TYPE_CHECKING:
    from ..core.daemon import Daemon

CONNECTED_WITHIN_S = 600.0


class BrowserUrls:
    """Remembers the last URL per browser and feeds the focused browser window."""

    def __init__(self, daemon: Daemon, source: UrlSource | None = None) -> None:
        self.daemon = daemon
        self.source = source
        self.last: dict[str, str] = {}
        self.latest_browser = ""
        self.last_seen: float = 0.0

    @property
    def url(self) -> str:
        return self.last.get(self.latest_browser, "")

    def on_url(self, browser: str, url: str) -> None:
        """A report arrived: remember it and let the daemon re-judge."""
        self.last[browser] = url
        self.latest_browser = browser
        self.last_seen = self.daemon.clock.now()
        if not self.daemon.on_url(browser, url):
            self.daemon.publish()

    def enrich(self, w: WindowInfo) -> WindowInfo:
        """Attach the last known URL to a freshly focused browser window (Hyprland knows no URL)."""
        if w.url or not self.daemon.is_browser(w.cls) or not self.last:
            return w
        key = next((b for b in self.last if b and (b.lower() in w.cls.lower() or w.cls.lower() in b.lower())),
                   self.latest_browser)
        return replace(w, url=self.last[key]) if self.last.get(key) else w

    def _age(self) -> float | None:
        return self.daemon.clock.now() - self.last_seen if self.last_seen else None

    def snapshot(self) -> dict:
        """The `browser` state section."""
        age = self._age()
        return {"enabled": self.daemon.cfg.browser_bridge.enabled, "url": self.url,
                "connected": age is not None and age < CONNECTED_WITHIN_S,
                "last_seen_ms": int(self.last_seen * 1000)}

    def status(self, _arg: object = None) -> dict:
        """Answer for `lockdock url`."""
        age = self._age()
        return {**self.snapshot(), "port": self.daemon.cfg.browser_bridge.port,
                "age_s": None if age is None else int(age),
                "listening": bool(getattr(self.source, "listening", False))}

    async def run(self) -> None:
        """Serve the bridge; a busy port is logged, not fatal."""
        assert self.source is not None
        try:
            await self.source.watch(self.on_url)
        except OSError as e:
            self.daemon.events.log("browser_bridge_error", error=str(e))


def install(daemon: Daemon) -> list[Awaitable[None]]:
    """Register the `browser` section, `url` command and focus enricher; serve when enabled."""
    cfg = daemon.cfg.browser_bridge
    feature = BrowserUrls(daemon, HttpUrlSource(cfg.port, cfg.token) if cfg.enabled else None)
    daemon.register_section("browser", feature.snapshot)
    daemon.register_command("url", feature.status)
    daemon.window_enrichers.append(feature.enrich)
    return [feature.run()] if cfg.enabled else []
