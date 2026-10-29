"""Holding notifications that do not belong to the current mode, and releasing them later."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .events import EventSink
from .models import Mode, Notification, NotificationDecision
from .ports import Classifier, NotificationSink
from .rules import matches
from .tasks import Spawn, spawn_task

RELEASE_ONE_BY_ONE_MAX = 5


def decide(mode: Mode, n: Notification) -> NotificationDecision:
    """Rules for one notification. action is `pass`, `hold` or `ask`."""
    rules = mode.notifications
    if n.urgency >= 2:
        return NotificationDecision("pass", "critical urgency")
    ident = f"{n.app}|{n.desktop_entry}"
    if p := matches(rules.hold_from, ident):
        return NotificationDecision("hold", f"hold_from '{p}'")
    if p := matches(rules.allow_from, ident):
        return NotificationDecision("pass", f"allow_from '{p}'")
    if p := matches(rules.pass_keywords, f"{n.summary}\n{n.body}"):
        return NotificationDecision("pass", f"keyword '{p}'")
    if rules.default in ("pass", "hold"):
        return NotificationDecision(rules.default, f"mode default '{rules.default}'")
    return NotificationDecision("ask", "mode default 'ask'")


@dataclass(frozen=True)
class OutgoingNotification:
    """A notification to (re)send through the NotificationSink."""

    app: str
    summary: str
    body: str
    desktop_entry: str = ""
    urgency: int = 1


def release_messages(held: list[Notification], why: str) -> list[OutgoingNotification]:
    """Up to 5 held notifications are re-sent one by one; more become one summary."""
    if len(held) <= RELEASE_ONE_BY_ONE_MAX:
        return [OutgoingNotification(n.app, n.summary, f"{n.body}\n({why})", n.desktop_entry, n.urgency)
                for n in held]
    apps: dict[str, int] = {}
    for n in held:
        apps[n.app] = apps.get(n.app, 0) + 1
    body = ", ".join(f"{a} ×{c}" for a, c in apps.items())
    return [OutgoingNotification("lockdock", f"{len(held)} notifications held {why}", body, urgency=1)]


class NotificationGate:
    """Decides pass/hold/ask per notification, keeps the held list, releases it.

    A held notification is closed as soon as the notification daemon replies
    with its id (`on_reply`).
    """

    def __init__(self, mode: Callable[[], Mode], classifier: Classifier, sink: NotificationSink,
                 events: EventSink, on_change: Callable[[], None], spawn: Spawn = spawn_task) -> None:
        self._mode = mode
        self.classifier = classifier
        self.sink = sink
        self.events = events
        self.on_change = on_change
        self.spawn = spawn
        self.held: list[Notification] = []
        # notifications to close, keyed by (sender, cookie) until the id reply arrives
        self._awaiting_id: dict[tuple[str, int], Notification] = {}

    def on_notify(self, n: Notification) -> None:
        d = decide(self._mode(), n)
        if d.action == "ask":
            # close it as soon as the id arrives; re-send if the verdict is "pass"
            self._awaiting_id[(n.sender, n.cookie)] = n
            self.spawn(self._ask(n))
            return
        self.events.log("notification", app=n.app, summary=n.summary, action=d.action, reason=d.reason)
        if d.action == "hold":
            self._awaiting_id[(n.sender, n.cookie)] = n
            self.held.append(n)
            self.on_change()

    async def _ask(self, n: Notification) -> None:
        action, reason = await self.classifier.notification(self._mode(), n)
        self.events.log("notification", app=n.app, summary=n.summary, action=action, reason=reason)
        if action == "pass":
            self.sink.send(n.app, n.summary, n.body, n.desktop_entry, n.urgency)
        else:
            self.held.append(n)
            self.on_change()

    def on_reply(self, cookie: int, nid: int, dest: str) -> None:
        n = self._awaiting_id.pop((dest, cookie), None)
        if n:
            n.id = nid
            self.sink.close(nid)

    def release(self, why: str) -> int:
        """Re-deliver everything held; returns how many were held."""
        count = len(self.held)
        if not count:
            return 0
        for m in release_messages(self.held, why):
            self.sink.send(m.app, m.summary, m.body, m.desktop_entry, m.urgency)
        self.events.log("release", count=count)
        self.held.clear()
        self.on_change()
        return count
