"""Holding notifications that do not belong to the current mode, and releasing them later."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .events import EventSink
from .models import Mode, Notification, NotificationDecision, NotificationVerdict
from .ports import Classifier, Clock, NotificationSink
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


DND_LABEL = "do not disturb"


@dataclass
class Held:
    """One held notification: when it was held, and where ("Writing", or "do not disturb")."""

    n: Notification
    at: float
    where: str
    dnd: bool = False


class NotificationGate:
    """Decides pass/hold/ask per notification, keeps the held list, releases it.

    A held notification is closed as soon as the notification daemon replies
    with its id (`on_reply`). `hold_listeners` are called with every notification
    that gets held, plus the classifier's verdict when one was asked (else None);
    not while `dnd` is on, which holds everything silently. `release_listeners` are
    called with every batch of notifications that leaves the held list. `expire(now)`
    re-delivers the ones held for `release_after_s()` seconds (0 = never).
    """

    def __init__(self, mode: Callable[[], Mode], classifier: Classifier, sink: NotificationSink,
                 events: EventSink, on_change: Callable[[], None], clock: Clock, spawn: Spawn = spawn_task,
                 release_after_s: Callable[[], float] = lambda: 0.0) -> None:
        self._mode = mode
        self.classifier = classifier
        self.sink = sink
        self.events = events
        self.on_change = on_change
        self.clock = clock
        self.spawn = spawn
        self.release_after_s = release_after_s
        self.dnd = False
        self._held: list[Held] = []
        self.hold_listeners: list[Callable[[Notification, NotificationVerdict | None], None]] = []
        self.release_listeners: list[Callable[[list[Notification]], None]] = []
        # notifications to close, keyed by (sender, cookie) until the id reply arrives
        self._awaiting_id: dict[tuple[str, int], Notification] = {}

    @property
    def held(self) -> list[Notification]:
        """The held notifications, oldest first."""
        return [h.n for h in self._held]

    def on_notify(self, n: Notification) -> None:
        if self.dnd:
            self.events.log("notification", app=n.app, summary=n.summary, action="hold", reason=DND_LABEL)
            self._awaiting_id[(n.sender, n.cookie)] = n
            self._hold(n, None)
            return
        d = decide(self._mode(), n)
        if d.action == "ask":
            # close it as soon as the id arrives; re-send if the verdict is "pass"
            self._awaiting_id[(n.sender, n.cookie)] = n
            self.spawn(self._ask(n))
            return
        self.events.log("notification", app=n.app, summary=n.summary, action=d.action, reason=d.reason)
        if d.action == "hold":
            self._awaiting_id[(n.sender, n.cookie)] = n
            self._hold(n, None)

    async def _ask(self, n: Notification) -> None:
        v = await self.classifier.notification(self._mode(), n)
        self.events.log("notification", app=n.app, summary=n.summary, action=v.action, reason=v.reason,
                        time_sensitive=v.time_sensitive, cached=v.cached)
        if v.action == "pass" and not self.dnd:
            self.sink.send(n.app, n.summary, n.body, n.desktop_entry, n.urgency)
        else:
            self._hold(n, v)

    def _hold(self, n: Notification, verdict: NotificationVerdict | None) -> None:
        dnd = self.dnd
        self._held.append(Held(n, self.clock.now(), DND_LABEL if dnd else self._mode().label, dnd))
        if not dnd:
            for listener in self.hold_listeners:
                listener(n, verdict)
        self.on_change()

    def on_reply(self, cookie: int, nid: int, dest: str) -> None:
        n = self._awaiting_id.pop((dest, cookie), None)
        if n:
            n.id = nid
            self.sink.close(nid)

    def release(self, why: str) -> int:
        """Re-deliver everything held; returns how many were held."""
        return self._release(list(self._held), why)

    def set_dnd(self, on: bool) -> int:
        """Turn do not disturb on or off. Off re-delivers what DND held; returns how many."""
        if on == self.dnd:
            return 0
        self.dnd = on
        released = 0 if on else self._release([h for h in self._held if h.dnd], f"while you were in {DND_LABEL}")
        self.events.log("dnd", on=on, released=released)
        self.on_change()
        return released

    def expire(self, now: float) -> int:
        """Re-deliver every notification held for `release_after_s()` or longer; returns how many."""
        limit = self.release_after_s()
        due = [h for h in self._held if limit > 0 and now - h.at >= limit]
        if not due:
            return 0
        groups: dict[str, list[Held]] = {}
        for h in due:
            groups.setdefault(h.where, []).append(h)
        for where, hs in groups.items():
            minutes = max(1, round((now - min(h.at for h in hs)) / 60))
            self._release(hs, f"held {minutes} min in {where}", reason="time limit", publish=False)
        self.on_change()
        return len(due)

    def _release(self, entries: list[Held], why: str, reason: str = "", publish: bool = True) -> int:
        if not entries:
            return 0
        notes = [h.n for h in entries]
        for m in release_messages(notes, why):
            self.sink.send(m.app, m.summary, m.body, m.desktop_entry, m.urgency)
        self.events.log("release", count=len(notes), **({"reason": reason} if reason else {}))
        gone = {id(h) for h in entries}
        self._held = [h for h in self._held if id(h) not in gone]
        for listener in self.release_listeners:
            listener(notes)
        if publish:
            self.on_change()
        return len(notes)
