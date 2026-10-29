"""Classifier and pet Speaker backed by `claude -p` (the user's Claude Code login; no API key), with a JSON file cache."""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path

from ..core.models import ActivityVerdict, Mode, Notification, NotificationVerdict, Verdict, WindowInfo
from ..core.rules import norm_title

ACTIVITY_SYS = (
    "You classify whether a desktop window is on task for a focus mode. "
    "Answer ONLY compact JSON: {\"verdict\":\"on\"|\"off\"|\"neutral\",\"reason\":\"<=12 words\"}. "
    "neutral = system/utility windows or genuinely ambiguous."
)
NOTIF_SYS = (
    "You decide whether a desktop notification should interrupt someone in a focus mode now, "
    "or be held until the mode ends. Answer ONLY compact JSON: "
    "{\"action\":\"pass\"|\"hold\",\"reason\":\"<=12 words\",\"time_sensitive\":true|false,"
    "\"deadline\":\"<=4 words\"|null}. Pass only if time-sensitive and relevant to the mode "
    "or clearly important (people waiting, failures, calendar in the next hour). "
    "time_sensitive = someone is waiting for an answer or something happens soon, whatever the action. "
    "deadline = the time it is needed by, as written or implied (e.g. \"3pm\", \"today\"), else null."
)
PET_SYS = (
    "You write one line of speech for a desktop pet that scolds its owner for being off task. "
    "Stay in this character: {persona} The pet's mood is {mood}. At most 12 words, playful, "
    "tease the distracting activity, never insult the person. "
    "Answer ONLY compact JSON: {{\"line\":\"...\"}}"
)


async def ask_claude(system: str, user: str, model: str, timeout_s: float) -> dict | None:
    """One `claude -p` call with no tools; the first JSON object in the reply, or None."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", "--no-session-persistence", "--model", model,
            "--output-format", "json", "--tools", "", "--system-prompt", system,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(proc.communicate(user.encode()), timeout=timeout_s)
        res = json.loads(out)
        if res.get("is_error"):
            return None
        m = re.search(r"\{.*\}", res.get("result", ""), re.S)
        return json.loads(m.group(0)) if m else None
    except (asyncio.TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None


def activity_key(mode: Mode, window: WindowInfo) -> str:
    """Cache key for a window verdict: (mode, class, normalised title). Shared by every classifier."""
    return f"a|{mode.id}|{window.cls}|{norm_title(window.title)}"


def notification_key(mode: Mode, n: Notification) -> str:
    """Cache key for a notification verdict: (mode, app, normalised summary)."""
    return f"n|{mode.id}|{n.app}|{norm_title(n.summary)}"


class JsonFileCache:
    """A dict persisted to one JSON file after every write."""

    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            self._data: dict[str, dict] = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            self._data = {}

    def get(self, key: str) -> dict | None:
        return self._data.get(key)

    def put(self, key: str, value: dict) -> None:
        self._data[key] = value
        self._save()

    def drop(self, key: str) -> bool:
        """Forget one entry; whether it was there."""
        if self._data.pop(key, None) is None:
            return False
        self._save()
        return True

    def _save(self) -> None:
        try:
            self.path.write_text(json.dumps(self._data, indent=1))
        except OSError:
            pass


class ClaudeCliClassifier:
    """Classifier port: one `claude -p` call at a time, no tools, results cached by
    (mode, class, normalised title) or (mode, app, normalised summary)."""

    provider = "claude"

    def __init__(self, cache: JsonFileCache, model: str = "haiku", timeout_s: float = 40) -> None:
        self.cache = cache
        self.model = model
        self.timeout_s = timeout_s
        self._sem = asyncio.Semaphore(1)

    async def _ask(self, system: str, user: str) -> dict | None:
        async with self._sem:
            return await ask_claude(system, user, self.model, self.timeout_s)

    async def activity(self, mode: Mode, window: WindowInfo) -> ActivityVerdict:
        key = activity_key(mode, window)
        if c := self.cache.get(key):
            return ActivityVerdict(Verdict(c["verdict"]), c["reason"] + " (cached)", cached=True)
        payload = {"mode": mode.label, "mode_description": mode.description, "mode_apps": mode.apps,
                   "window_class": window.cls, "window_title": window.title}
        if window.url:
            payload["window_url"] = window.url
        res = await self._ask(ACTIVITY_SYS, json.dumps(payload))
        if not res or res.get("verdict") not in ("on", "off", "neutral"):
            return ActivityVerdict(Verdict.NEUTRAL, "classifier unavailable")
        self.cache.put(key, {"verdict": res["verdict"], "reason": res.get("reason", ""), "ts": time.time()})
        return ActivityVerdict(Verdict(res["verdict"]), res.get("reason", ""))

    async def notification(self, mode: Mode, n: Notification) -> NotificationVerdict:
        key = notification_key(mode, n)
        if c := self.cache.get(key):
            return NotificationVerdict(c["action"], c["reason"], bool(c.get("time_sensitive")),
                                       c.get("deadline"), cached=True)
        user = json.dumps({"mode": mode.label, "mode_description": mode.description,
                           "app": n.app, "summary": n.summary, "body": n.body[:400]})
        res = await self._ask(NOTIF_SYS, user)
        if not res or res.get("action") not in ("pass", "hold"):
            return NotificationVerdict("pass", "classifier unavailable (fail open)")
        deadline = str(res.get("deadline") or "").strip()[:40] or None
        v = NotificationVerdict(res["action"], res.get("reason", ""), res.get("time_sensitive") is True, deadline)
        self.cache.put(key, {"action": v.action, "reason": v.reason, "time_sensitive": v.time_sensitive,
                             "deadline": v.deadline, "ts": time.time()})
        return v


class ClaudeCliSpeaker:
    """Speaker port: one scolding line per (mood, app) from `claude -p`, cached in a JsonFileCache."""

    def __init__(self, cache: JsonFileCache, persona: str, model: str = "haiku", timeout_s: float = 40) -> None:
        self.cache = cache
        self.persona = persona
        self.model = model
        self.timeout_s = timeout_s
        self._sem = asyncio.Semaphore(1)

    async def line(self, mood: str, mode: str, app: str, title: str, reason: str) -> str | None:
        key = f"p|{mood}|{app}"
        if c := self.cache.get(key):
            return c["line"]
        user = json.dumps({"mood": mood, "focus_mode": mode, "app": app, "window_title": title[:120],
                           "why_off_task": reason})
        async with self._sem:
            res = await ask_claude(PET_SYS.format(persona=self.persona, mood=mood), user, self.model,
                                   self.timeout_s)
        text = str((res or {}).get("line", "")).strip()
        if not text or len(text.split()) > 16:
            return None
        self.cache.put(key, {"line": text, "ts": time.time()})
        return text
