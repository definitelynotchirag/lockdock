"""Decision prompts: cards the dock shows when a choice is the user's to make.

Three kinds, all published as the `prompts` state section (newest last, at most MAX_OPEN):

- `site`: the focused window is off task here but belongs to another mode X
  ("x.com · belongs to Social · [Stay] [Go to Social (30s wait)]").
- `notification`: a held notification, with [Later] and, when another mode
  would let it through, [Go to X].
- `verdict`: a fresh classifier verdict on something no mode knows; no actions,
  fades after VERDICT_TTL_S.

"Go to X" is the ordinary mode request, so it starts (or presses) the exit countdown.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .events import EventSink
from .models import Config, Mode, Notification, NotificationVerdict, WindowInfo
from .ports import Classifier, Clock
from .rules import matches
from .tasks import Spawn, spawn_task

MAX_OPEN = 3
VERDICT_TTL_S = 6.0
BODY_MAX = 160
CLOSE_ACTIONS = ("later", "dismiss")


@dataclass
class Prompt:
    """One open decision card. `target` (a host or window class) keys snoozing and dedup."""

    id: str
    kind: str                       # notification | site | verdict
    created: float
    expires: float | None
    icon: str
    title: str
    subtitle: str
    body: str = ""
    tag: dict | None = None
    actions: list[dict] = field(default_factory=list)
    target: str = ""

    def to_dict(self) -> dict:
        """The form published in state.json `prompts`."""
        return {"id": self.id, "kind": self.kind, "created_ms": int(self.created * 1000),
                "expires_ms": None if self.expires is None else int(self.expires * 1000),
                "icon": self.icon, "title": self.title, "subtitle": self.subtitle, "body": self.body,
                "tag": self.tag, "actions": [dict(a) for a in self.actions]}

    def action(self, action_id: str) -> dict | None:
        return next((a for a in self.actions if a["id"] == action_id), None)


def host_of(url: str | None) -> str:
    """The host of a URL without a leading `www.` ("" when there is none)."""
    if not url:
        return ""
    try:
        host = urlsplit(url if "//" in url else f"//{url}").hostname or ""
    except ValueError:
        return ""
    return host.removeprefix("www.")


def is_catch_all(mode: Mode) -> bool:
    """A mode whose on_task has a pattern matching everything (like `.*`): it claims no site."""
    for p in mode.on_task:
        try:
            if re.search(p, ""):
                return True
        except re.error:
            continue
    return False


def _is_app_of(cls: str, apps: list[str]) -> bool:
    c = cls.lower()
    return bool(c) and any(c == a.lower() or c in a.lower() for a in apps)


def belongs_to(cfg: Config, current: Mode, w: WindowInfo) -> Mode | None:
    """The first other mode (modes.json order) whose `on_task` rules or `apps` claim this window.

    Skips the current mode, catch-all modes, and modes whose `off_task` matches the window.
    Browsers are never claimed by being a mode app (same as rule_activity).
    """
    text = f"{w.cls}|{w.title}|{w.url or ''}"
    is_browser = any(b.lower() in w.cls.lower() for b in cfg.browsers)
    for m in cfg.modes:
        if m.id == current.id or is_catch_all(m) or matches(m.off_task, text):
            continue
        if matches(m.on_task, text) or (not is_browser and _is_app_of(w.cls, m.apps)):
            return m
    return None


def held_for(cfg: Config, current: Mode, n: Notification) -> Mode | None:
    """The first other mode whose `notifications.allow_from` or `apps` matches the notification's app."""
    ident = f"{n.app}|{n.desktop_entry}"
    for m in cfg.modes:
        if m.id == current.id or matches(m.notifications.hold_from, ident):
            continue
        if matches(m.notifications.allow_from, ident) or any(
                a.lower() in (n.app.lower(), n.desktop_entry.lower()) for a in m.apps):
            return m
    return None


def switch_action(target: Mode, wait_s: int) -> dict:
    """The primary "Go to X (Ns wait)" button; the wait is the current mode's exit delay."""
    label = f"Go to {target.label}" + (f" ({wait_s}s wait)" if wait_s > 0 else "")
    return {"id": "switch", "label": label, "style": "primary", "mode": target.id}


def notification_tag(v: NotificationVerdict | None) -> dict | None:
    """The card's tag: urgent when the classifier says someone is waiting, else none."""
    if not v or not v.time_sensitive:
        return None
    detail = f"needs your answer before {v.deadline}" if v.deadline else v.reason
    return {"label": "Time-sensitive", "detail": detail, "level": "urgent"}


def _truncate(text: str, limit: int = BODY_MAX) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


class PromptCenter:
    """Opens, publishes and resolves decision prompts.

    Inputs: `on_activity` (every final verdict), `on_held` (every held notification),
    `on_switch` (a mode switch clears the cards and the snoozes), `act` (a button press),
    `tick` (once a second: purge expired cards). `request(mode_id)` is ModeManager.request.
    """

    def __init__(self, config: Callable[[], Config], mode: Callable[[], Mode],
                 request: Callable[[str], str], classifier: Classifier, clock: Clock, events: EventSink,
                 on_change: Callable[[], None], spawn: Spawn = spawn_task) -> None:
        self._config = config
        self._mode = mode
        self._request = request
        self.classifier = classifier
        self.clock = clock
        self.events = events
        self.on_change = on_change
        self.spawn = spawn
        self.prompts: list[Prompt] = []
        self._snoozed: dict[str, float] = {}   # site target -> no new card before this time
        self._seq = 0

    # ---------- inputs ----------
    def on_activity(self, activity: dict) -> None:
        """A final verdict: open a site card or a verdict toast when one is due."""
        cfg = self._config()
        pc = cfg.prompts
        verdict, app = activity.get("verdict"), activity.get("app") or ""
        if not pc.enabled or not app or verdict not in ("on", "off"):
            return
        w = WindowInfo(app, activity.get("title", ""), activity.get("url"))
        mode = self._mode()
        target = host_of(w.url) or w.cls
        other = belongs_to(cfg, mode, w)
        if verdict == "off" and other:
            if pc.site_cards:
                self._open_site(mode, other, w, target)
            return
        if other or activity.get("source") != "llm" or not pc.verdict_toasts:
            return
        tag = ({"label": f"Fits {mode.label}", "detail": activity.get("reason", ""), "level": "ok"}
               if verdict == "on" else
               {"label": "Off task", "detail": activity.get("reason", ""), "level": "urgent"})
        self._close_where(lambda p: p.kind == "verdict" and p.target == target)
        now = self.clock.now()
        self._open(Prompt(self._next_id(), "verdict", now, now + VERDICT_TTL_S, w.cls, target,
                          "not in any mode", "", tag, [], target))

    def on_held(self, n: Notification, verdict: NotificationVerdict | None) -> None:
        """A notification was held: open its card; ask the classifier for the tag when nobody did."""
        cfg = self._config()
        if not (cfg.prompts.enabled and cfg.prompts.notification_cards):
            return
        mode = self._mode()
        other = held_for(cfg, mode, n)
        actions = [{"id": "later", "label": "Later", "style": "plain"}]
        if other and other.id != mode.id:
            actions.append(switch_action(other, mode.exit_delay_s))
        subtitle = f"{n.app} · held for {other.label}" if other else f"{n.app} · held in {mode.label}"
        p = Prompt(self._next_id(), "notification", self.clock.now(), None, n.desktop_entry or n.app,
                   n.summary, subtitle, _truncate(n.body), notification_tag(verdict), actions,
                   f"{n.app}|{n.summary}")
        self._open(p)
        if verdict is None and cfg.llm_enabled:
            self.spawn(self._fetch_tag(p.id, mode, n))

    def on_switch(self, old: Mode, new: Mode) -> None:
        """A new mode: every card is stale (held notifications were released) and snoozes reset."""
        self._snoozed.clear()
        if self.prompts:
            self.prompts.clear()
            self.on_change()

    def tick(self) -> None:
        """Purge expired cards."""
        now = self.clock.now()
        gone = [p for p in self.prompts if p.expires is not None and p.expires <= now]
        if not gone:
            return
        self.prompts = [p for p in self.prompts if p not in gone]
        for p in gone:
            self.events.log("prompt", op="expire", id=p.id, prompt_kind=p.kind, title=p.title)
        self.on_change()

    # ---------- actions ----------
    def act(self, prompt_id: str, action: str) -> str:
        """A button: later/dismiss close, stay closes and snoozes the target, switch requests the mode."""
        p = next((q for q in self.prompts if q.id == prompt_id), None)
        if not p:
            return f"no open prompt {prompt_id!r}"
        btn = p.action(action)
        if action not in CLOSE_ACTIONS + ("stay",) and not btn:
            return f"prompt {prompt_id} has no action {action!r}"
        self.prompts.remove(p)
        result = "dismissed"
        if action == "stay":
            self._snooze(p.target)
            result = f"staying; no card for {p.target} for {self._config().prompts.stay_snooze_s}s"
        elif action == "switch" and btn and btn.get("mode"):
            result = self._request(btn["mode"])
        self.events.log("prompt", op="act", id=p.id, prompt_kind=p.kind, action=action, title=p.title,
                        result=result)
        self.on_change()
        return result

    def handle_act(self, arg: Any) -> str:
        """`prompt_act` control command: `{"id", "action"}` (or `[id, action]`)."""
        if isinstance(arg, dict):
            pid, action = arg.get("id"), arg.get("action")
        elif isinstance(arg, (list, tuple)) and len(arg) == 2:
            pid, action = arg
        else:
            return 'usage: prompt_act {"id": "p1", "action": "later|dismiss|stay|switch"}'
        return self.act(str(pid), str(action))

    def snapshot(self) -> list[dict]:
        """The `prompts` state section, newest last."""
        return [p.to_dict() for p in self.prompts]

    # ---------- internals ----------
    def _open_site(self, mode: Mode, other: Mode, w: WindowInfo, target: str) -> None:
        now = self.clock.now()
        if self._snoozed.get(target, 0.0) > now or any(
                p.kind == "site" and p.target == target for p in self.prompts):
            return
        self._snooze(target)
        # one site card per window class: a browser judged first by title (target = class), then by
        # URL (target = host), or a new tab in the same browser, replaces its older card
        self._close_where(lambda p: p.kind == "site" and p.icon == w.cls)
        actions = [{"id": "stay", "label": "Stay", "style": "plain"}, switch_action(other, mode.exit_delay_s)]
        self._open(Prompt(self._next_id(), "site", now, None, w.cls, target, f"belongs to {other.label}",
                          "Stay focused, or switch?", None, actions, target))

    def _snooze(self, target: str) -> None:
        self._snoozed[target] = self.clock.now() + self._config().prompts.stay_snooze_s

    def _open(self, p: Prompt) -> None:
        self.prompts.append(p)
        while len(self.prompts) > MAX_OPEN:
            old = self.prompts.pop(0)
            self.events.log("prompt", op="drop", id=old.id, prompt_kind=old.kind, title=old.title)
        self.events.log("prompt", op="open", id=p.id, prompt_kind=p.kind, title=p.title, subtitle=p.subtitle,
                        tag=p.tag)
        self.on_change()

    def _close_where(self, pred: Callable[[Prompt], bool]) -> None:
        self.prompts = [p for p in self.prompts if not pred(p)]

    def _next_id(self) -> str:
        self._seq += 1
        return f"p{self._seq}"

    async def _fetch_tag(self, prompt_id: str, mode: Mode, n: Notification) -> None:
        """Ask the classifier whether a rule-held notification is time-sensitive (cached per app+summary)."""
        v = await self.classifier.notification(mode, n)
        p = next((q for q in self.prompts if q.id == prompt_id), None)
        tag = notification_tag(v)
        if p and tag:
            p.tag = tag
            self.events.log("prompt", op="tag", id=p.id, prompt_kind=p.kind, tag=tag)
            self.on_change()
