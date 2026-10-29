"""Observe org.freedesktop.Notifications traffic without owning the name.

We run `busctl monitor` and parse Notify calls plus their replies (which carry
the id). Holding a notification = closing it right after the daemon shows it
and remembering it for later release.
"""
from __future__ import annotations

import asyncio
import json
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field

OUR_HINT = "x-lockdock"


@dataclass
class Notification:
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
        return {"app": self.app, "summary": self.summary, "body": self.body[:200],
                "urgency": self.urgency, "ts": self.ts, "id": self.id}


def _decode(v):
    if isinstance(v, dict) and "data" in v:
        return v["data"]
    return v


async def watch(on_notify: Callable[[Notification], None], on_reply: Callable[[int, int, str], None]) -> None:
    """on_notify(n) for each Notify call; on_reply(cookie, id, sender) when the daemon answers."""
    cmd = ["busctl", "--user", "monitor", "--json=short",
           "--match", "type='method_call',interface='org.freedesktop.Notifications',member='Notify'",
           "--match", "type='method_return',sender='org.freedesktop.Notifications'"]
    while True:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.DEVNULL)
        assert proc.stdout
        while line := await proc.stdout.readline():
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            if m.get("member") == "Notify" and m.get("type") == "method_call":
                data = m["payload"]["data"]
                hints = {k: _decode(v) for k, v in (data[6] or {}).items()}
                if OUR_HINT in hints:
                    continue  # our own re-delivery; do not loop
                on_notify(Notification(
                    app=data[0], summary=data[3], body=data[4],
                    urgency=int(hints.get("urgency", 1)), desktop_entry=str(hints.get("desktop-entry", "")),
                    ts=m.get("timestamp-realtime", 0) / 1e6, sender=m.get("sender", ""),
                    cookie=int(m.get("cookie", 0)), hints=hints))
            elif m.get("type") == "method_return":
                p = m.get("payload") or {}
                if p.get("type") == "u":
                    on_reply(int(m.get("reply_cookie", 0)), int(p["data"][0]), m.get("destination", ""))
        await asyncio.sleep(2)


def close(nid: int) -> None:
    subprocess.Popen(["busctl", "--user", "call", "org.freedesktop.Notifications",
                      "/org/freedesktop/Notifications", "org.freedesktop.Notifications",
                      "CloseNotification", "u", str(nid)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def send(app: str, summary: str, body: str, desktop_entry: str = "", urgency: int = 1,
         timeout_ms: int = -1) -> None:
    hints = ["x-lockdock", "b", "true", "urgency", "y", str(urgency)]
    n = 2
    if desktop_entry:
        hints += ["desktop-entry", "s", desktop_entry]
        n += 1
    subprocess.Popen(["busctl", "--user", "call", "org.freedesktop.Notifications",
                      "/org/freedesktop/Notifications", "org.freedesktop.Notifications",
                      "Notify", "susssasa{sv}i", app, "0", "", summary, body, "0", str(n), *hints,
                      str(timeout_ms)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def quote(s: str) -> str:
    return shlex.quote(s)
