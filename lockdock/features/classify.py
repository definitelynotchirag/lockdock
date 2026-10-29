"""`classify` control verb: run the configured classifier once on a made-up window, for tuning
mode descriptions (`lockdock classify "<class>" "<title>" [--mode writing]`)."""
from __future__ import annotations

import time
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any

from ..adapters.claude_cli import activity_key
from ..core.activity import rule_activity
from ..core.models import WindowInfo

if TYPE_CHECKING:
    from ..core.daemon import Daemon


async def classify(daemon: Daemon, arg: Any) -> dict | str:
    """arg: {cls, title, mode?, url?, cached?}. Without `cached`, the cache entry for this window
    is dropped first, so the answer is live (and re-cached for the daemon)."""
    arg = arg if isinstance(arg, dict) else {}
    mode = daemon.cfg.get(arg["mode"]) if arg.get("mode") else daemon.modes.cur
    if mode is None:
        return f"no mode {arg.get('mode')!r} (see: lockdock modes)"
    w = WindowInfo(cls=str(arg.get("cls", "")), title=str(arg.get("title", "")), url=arg.get("url") or None)
    rule = rule_activity(mode, w, daemon.cfg.browsers)
    classifier = daemon.classifier
    cache = getattr(classifier, "cache", None)
    if not arg.get("cached") and cache is not None and hasattr(cache, "drop"):
        cache.drop(activity_key(mode, w))
    t0 = time.monotonic()
    answer = await classifier.activity(mode, w)
    ms = round((time.monotonic() - t0) * 1000)
    return {"mode": mode.id, "provider": getattr(classifier, "provider", type(classifier).__name__),
            "verdict": answer.verdict.value, "reason": answer.reason,
            "source": "cache" if answer.cached else "llm", "ms": ms,
            "rules": ({"verdict": rule[0].value, "reason": rule[1]} if rule else None)}


def install(daemon: Daemon) -> list[Awaitable[None]]:
    daemon.register_command("classify", lambda arg: classify(daemon, arg))
    return []
