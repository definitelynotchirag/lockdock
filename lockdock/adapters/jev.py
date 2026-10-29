"""Classifier backed by Jev (TypeSafe AI): a hosted decision model with typed answers and
probabilities, ~100-500 ms per call. One HTTPS POST per question set, stdlib urllib in a thread.

The API key is only ever put in the Authorization header: never logged, never cached.
"""
from __future__ import annotations

import asyncio
import json
import re
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from ..core.models import ActivityVerdict, Mode, Notification, NotificationVerdict, Verdict, WindowInfo
from .claude_cli import JsonFileCache, activity_key, notification_key

API_URL = "https://api.typesafe.ai/v1/systemone"
TIME_SENSITIVE_AT = 0.5   # noul probability from which a notification counts as time-sensitive

ACTIVITY_INSTRUCTIONS = (
    "The user switched on the focus mode `{label}`, described in state.focus_mode. state.window is the "
    "window they are looking at right now (application class, window title, and the page URL for a "
    "browser). For a browser, judge the page by its title and URL, not by the browser being allowed. "
    "Decide whether this window serves the work the mode is for."
)
ACTIVITY_CRITERIA = {
    "on": ("On task for {label}. The window is work the mode describes ({description}), or one of the "
           "mode's own apps used for that work ({apps}), or a page like the ones the user listed as on "
           "task ({on_task}). Reference material, documentation and tools that support the described "
           "work count as on task."),
    "off": ("Off task for {label}. The window is a distraction from the described work: a page like the "
            "ones the user listed as off task ({off_task}), or social media feeds, chat, video, news, "
            "games or shopping, or material for a different kind of work than the mode describes."),
    "neutral": ("Neither: a system or utility window (launcher, file picker, settings, password manager, "
                "lock screen, notification), an empty or new tab, or a page whose title gives no hint of "
                "what it is."),
}
NOTIF_INSTRUCTIONS = (
    "The user is in the focus mode `{label}`, described in state.focus_mode. state.notification just "
    "arrived. Decide whether it should interrupt them now, or be held until the mode ends."
)
NOTIF_CRITERIA = {
    "pass": ("Interrupt now: a real person is waiting for an answer or a decision from the user, or "
             "something breaks or happens within the next hour (an outage, a failed deploy, a meeting "
             "about to start), or the message is about the work the mode describes."),
    "hold": ("Hold until the mode ends: newsletters, promotions, social media activity, likes, "
             "follows, group chatter, digests, reminders with no deadline today, or anything that can "
             "wait an hour without consequence."),
}
URGENT_INSTRUCTIONS = (
    "Time-sensitive: does this notification need action from the user within the hour (someone is "
    "waiting for their answer, or something they must act on happens soon)?"
)

UsageFn = Callable[[dict[str, Any]], None]
Opener = Callable[..., Any]   # urllib.request.urlopen(request, timeout=...)


class JevError(Exception):
    """A failed Jev call; str() is a short reason safe to log (never contains the key)."""


def readable_rules(patterns: list[str]) -> str:
    """Turn the mode's regexes into plain words for the model: `twitter|x\\.com` -> `twitter, x.com`."""
    words: list[str] = []
    for p in patterns:
        if p in (".*", ".+"):
            words.append("anything")
            continue
        for alt in p.split("|"):
            w = re.sub(r"\\(.)", r"\1", alt).strip("^$ ").replace(".*", " ").strip()
            if w and w not in words:
                words.append(w)
    return ", ".join(words) or "none listed"


def mode_state(mode: Mode) -> dict[str, Any]:
    """The focus mode as Jev sees it: its brief, its apps and its rule lists in plain words."""
    return {"name": mode.label, "description": mode.description, "apps": mode.apps,
            "on_task_examples": readable_rules(mode.on_task),
            "off_task_examples": readable_rules(mode.off_task)}


def activity_request(mode: Mode, window: WindowInfo, model: str) -> dict[str, Any]:
    """The /v1/systemone body for one window: one `choice` question, on / off / neutral."""
    fmt = {"label": mode.label, "description": mode.description or "no description",
           "apps": ", ".join(mode.apps) or "none", "on_task": readable_rules(mode.on_task),
           "off_task": readable_rules(mode.off_task)}
    win: dict[str, Any] = {"app_class": window.cls, "title": window.title}
    if window.url:
        win["url"] = window.url
    return {"model": model, "state": {"focus_mode": mode_state(mode), "window": win},
            "questions": {"fit": {"type": "choice", "instructions": ACTIVITY_INSTRUCTIONS.format(**fmt),
                                  "criteria": {k: v.format(**fmt) for k, v in ACTIVITY_CRITERIA.items()}}}}


def notification_request(mode: Mode, n: Notification, model: str) -> dict[str, Any]:
    """The body for one notification: a pass/hold `choice` and a time-sensitive `noul`, one request."""
    state = {"focus_mode": {"name": mode.label, "description": mode.description},
             "notification": {"app": n.app, "summary": n.summary, "body": n.body[:400]}}
    return {"model": model, "state": state,
            "questions": {"deliver": {"type": "choice", "instructions": NOTIF_INSTRUCTIONS.format(label=mode.label),
                                      "criteria": dict(NOTIF_CRITERIA)},
                          "urgent": {"type": "noul", "instructions": URGENT_INSTRUCTIONS}}}


def _short(e: BaseException) -> str:
    if isinstance(e, urllib.error.HTTPError):
        return f"http {e.code}"
    if isinstance(e, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(e, urllib.error.URLError):
        return "timeout" if isinstance(e.reason, (TimeoutError, socket.timeout)) else f"network: {e.reason}"[:60]
    return f"{type(e).__name__}"[:60]


def _retryable(e: BaseException) -> bool:
    if isinstance(e, urllib.error.HTTPError):
        return e.code >= 500
    return isinstance(e, (TimeoutError, socket.timeout, urllib.error.URLError))


class JevClassifier:
    """Classifier port over Jev. Never raises: a failed call answers neutral (windows) or pass
    (notifications, fail open) with reason "jev unavailable: <why>". Results share the
    JsonFileCache and its keys with ClaudeCliClassifier. `on_usage(record)` hears every call:
    `{provider, op, model, ms, input_tokens, output_tokens}` or `{provider, op, ms, error}`."""

    provider = "jev"

    def __init__(self, cache: JsonFileCache, api_key: str, model: str = "jev-latest",
                 min_confidence: float = 0.35, timeout_s: float = 5.0, url: str = API_URL,
                 urlopen: Opener = urllib.request.urlopen, on_usage: UsageFn | None = None) -> None:
        self.cache = cache
        self._key = api_key
        self.model = model
        self.min_confidence = min_confidence
        self.timeout_s = timeout_s
        self.url = url
        self.urlopen = urlopen
        self.on_usage = on_usage
        self._sem = asyncio.Semaphore(2)

    def __repr__(self) -> str:   # keep the key out of any accidental repr / log line
        return f"JevClassifier(model={self.model!r})"

    # ---------- transport ----------
    def _post_once(self, body: bytes) -> dict:
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Authorization": f"Bearer {self._key}", "Content-Type": "application/json",
            "Accept": "application/json"})
        with self.urlopen(req, timeout=self.timeout_s) as r:
            return json.loads(r.read())

    def _post(self, payload: dict) -> dict:
        """POST with one retry on 5xx / timeout / network errors. Raises JevError."""
        body = json.dumps(payload).encode()
        for attempt in (1, 2):
            try:
                return self._post_once(body)
            except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
                if attempt == 2 or not _retryable(e):
                    detail = ""
                    if isinstance(e, urllib.error.HTTPError):
                        try:
                            detail = str(json.loads(e.read()).get("detail", ""))[:80]
                        except (ValueError, OSError, AttributeError):
                            pass
                    raise JevError(_short(e) + (f" {detail}" if detail else "")) from None
            except Exception as e:  # bad JSON, odd transport errors: never into the daemon
                raise JevError(_short(e)) from None
        raise JevError("unreachable")

    async def _ask(self, op: str, payload: dict) -> dict:
        """Run one request in a thread; returns `answers`. Reports usage. Raises JevError."""
        t0 = time.monotonic()
        async with self._sem:
            try:
                res = await asyncio.to_thread(self._post, payload)
            except JevError as e:
                self._report({"provider": "jev", "op": op, "ms": _ms(t0), "error": str(e)})
                raise
        usage = res.get("usage") or {}
        self._report({"provider": "jev", "op": op, "model": res.get("model", self.model), "ms": _ms(t0),
                      "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")})
        answers = res.get("answers")
        if not isinstance(answers, dict):
            raise JevError("no answers in response")
        return answers

    def _report(self, rec: dict) -> None:
        if self.on_usage:
            try:
                self.on_usage(rec)
            except Exception:  # a logging failure must not break classification
                pass

    # ---------- Classifier port ----------
    async def activity(self, mode: Mode, window: WindowInfo) -> ActivityVerdict:
        key = activity_key(mode, window)
        if c := self.cache.get(key):
            return ActivityVerdict(Verdict(c["verdict"]), c["reason"] + " (cached)", cached=True)
        try:
            ans = (await self._ask("activity", activity_request(mode, window, self.model))).get("fit") or {}
            choice, conf = ans.get("choice"), float(ans.get("confidence", 0.0))
            if choice not in ("on", "off", "neutral"):
                raise JevError(f"unexpected choice {choice!r}"[:60])
        except (JevError, TypeError, ValueError) as e:
            return ActivityVerdict(Verdict.NEUTRAL, f"jev unavailable: {e}")
        if conf < self.min_confidence:
            verdict, reason = Verdict.NEUTRAL, f"low confidence (p={conf:.2f} {choice}) · jev"
        else:
            verdict, reason = Verdict(choice), f"{choice} p={conf:.2f} · jev"
        self.cache.put(key, {"verdict": verdict.value, "reason": reason, "ts": time.time()})
        return ActivityVerdict(verdict, reason)

    async def notification(self, mode: Mode, n: Notification) -> NotificationVerdict:
        key = notification_key(mode, n)
        if c := self.cache.get(key):
            return NotificationVerdict(c["action"], c["reason"], bool(c.get("time_sensitive")),
                                       c.get("deadline"), cached=True)
        try:
            answers = await self._ask("notification", notification_request(mode, n, self.model))
            dec, urg = answers.get("deliver") or {}, answers.get("urgent") or {}
            action, conf = dec.get("choice"), float(dec.get("confidence", 0.0))
            p_urgent = float(urg.get("noul", 0.0))
            if action not in ("pass", "hold"):
                raise JevError(f"unexpected choice {action!r}"[:60])
        except (JevError, TypeError, ValueError) as e:
            return NotificationVerdict("pass", f"jev unavailable: {e} (fail open)")
        urgent = p_urgent >= TIME_SENSITIVE_AT
        if conf < self.min_confidence:
            reason, action = f"low confidence (p={conf:.2f} {action}), fail open", "pass"
        else:
            reason = f"{action} p={conf:.2f}"
        if urgent:
            reason = f"needs action within the hour (p={p_urgent:.2f}) · {reason}"
        v = NotificationVerdict(action, reason + " · jev", urgent, None)
        self.cache.put(key, {"action": v.action, "reason": v.reason, "time_sensitive": v.time_sensitive,
                             "deadline": None, "ts": time.time()})
        return v


def _ms(t0: float) -> int:
    return round((time.monotonic() - t0) * 1000)
