"""Judging the focused window against the current mode: dwell, rules, then the classifier."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace

from .events import EventSink
from .models import Config, Mode, Verdict, WindowInfo
from .ports import Classifier, Clock
from .rules import matches
from .tasks import Spawn, spawn_task


def rule_activity(mode: Mode, window: WindowInfo, browsers: list[str] | tuple[str, ...] = ()
                  ) -> tuple[Verdict, str] | None:
    """Decide by rules alone; None means "ask the classifier"."""
    cls = window.cls
    text = f"{cls}|{window.title}|{window.url or ''}"
    if p := matches(mode.off_task, text):
        return Verdict.OFF, f"matches off_task rule '{p}'"
    if p := matches(mode.on_task, text):
        return Verdict.ON, f"matches on_task rule '{p}'"
    is_browser = any(b.lower() in cls.lower() for b in browsers)
    is_mode_app = bool(cls) and any(cls.lower() == a.lower() or cls.lower() in a.lower() for a in mode.apps)
    if is_mode_app and not is_browser:
        return Verdict.ON, "mode app"
    # a browser is judged by its tab title, never by being a mode app
    if mode.unknown == "neutral":
        return Verdict.NEUTRAL, "unknown app (mode treats unknown as neutral)"
    if mode.unknown == "off":
        return Verdict.OFF, "unknown app (mode treats unknown as off task)"
    return None


class ActivityJudge:
    """Tracks the focused window and publishes a verdict once it has been focused for dwell_s.

    `activity` is the dict published in state.json: verdict, reason, app, title, source (+ url).
    `source` says where the verdict came from: `rule` (rules, policies, no window, llm off),
    `llm` (a live classifier call) or `cache` (the classifier answered from its cache).
    """

    def __init__(self, config: Callable[[], Config], mode: Callable[[], Mode], classifier: Classifier,
                 clock: Clock, events: EventSink, on_change: Callable[[], None],
                 on_off_task: Callable[[Mode, WindowInfo, str], None],
                 spawn: Spawn = spawn_task, on_verdict: Callable[[dict], None] | None = None) -> None:
        self._config = config
        self._mode = mode
        self.classifier = classifier
        self.clock = clock
        self.events = events
        self.on_change = on_change
        self.on_off_task = on_off_task
        self.spawn = spawn
        self.on_verdict = on_verdict
        self.focus = WindowInfo()
        self.activity: dict = {}
        self._task: asyncio.Task[None] | None = None

    def on_focus(self, window: WindowInfo) -> None:
        """Focus changed: restart the dwell timer."""
        self.focus = window
        self.schedule()

    def set_url(self, url: str) -> bool:
        """The focused window's URL changed: re-judge. False when there is nothing to change."""
        if not self.focus.cls or self.focus.url == url:
            return False
        self.focus = replace(self.focus, url=url)
        self.schedule()
        return True

    def schedule(self) -> None:
        """(Re)judge the current focus after the dwell time."""
        if self._task:
            self._task.cancel()
        self._task = self.spawn(self._judge_after_dwell())

    async def _judge_after_dwell(self) -> None:
        await self.clock.sleep(self._config().dwell_s)
        await self.judge()

    def _set(self, verdict: Verdict, reason: str, w: WindowInfo, source: str = "rule") -> None:
        self.activity = {"verdict": verdict.value, "reason": reason, "app": w.cls, "title": w.title,
                         "source": source}
        if w.url:
            self.activity["url"] = w.url

    async def judge(self) -> None:
        """Judge the current focus now (rules, then classifier) and publish the verdict."""
        w, mode, cfg = self.focus, self._mode(), self._config()
        if not w.cls:
            self._set(Verdict.NEUTRAL, "no window", w)
            self._verdict_done()
            return
        res = rule_activity(mode, w, cfg.browsers)
        source = "rule"
        if res is None:
            if cfg.llm_enabled:
                self._set(Verdict.NEUTRAL, "classifying…", w, "llm")
                self.on_change()
                answer = await self.classifier.activity(mode, w)
                res, source = (answer.verdict, answer.reason), ("cache" if answer.cached else "llm")
            else:
                res = (Verdict.NEUTRAL, "unknown app, llm disabled")
        if w.key() != self.focus.key():
            return  # focus moved on while we were thinking
        verdict, reason = res
        prev = self.activity.get("verdict")
        self._set(verdict, reason, w, source)
        self.events.log("activity", app=w.cls, title=w.title, verdict=verdict.value, reason=reason,
                        source=source)
        if verdict == Verdict.OFF and prev != Verdict.OFF.value and mode.off_task_action == "notify":
            self.on_off_task(mode, w, reason)
        self._verdict_done()

    def _verdict_done(self) -> None:
        """A final verdict (not "classifying…"): tell the listener, then publish."""
        if self.on_verdict:
            self.on_verdict(dict(self.activity))
        self.on_change()
