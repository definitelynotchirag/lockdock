"""Classify activity and notifications against the current mode.

Rules first (free, instant). Unknowns go to `claude -p --model haiku` with no
tools, cached by (mode, class, normalised title). The CLI uses the user's own
Claude Code login, so no API key is needed.
"""
from __future__ import annotations

import asyncio
import json
import re
import time

from .modes import Mode, Notifications
from .paths import CACHE_FILE

_cache: dict[str, dict] = {}
_sem = asyncio.Semaphore(1)
MODEL = "haiku"


def load_cache() -> None:
    global _cache
    try:
        _cache = json.loads(CACHE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        _cache = {}


def _save_cache() -> None:
    try:
        CACHE_FILE.write_text(json.dumps(_cache, indent=1))
    except OSError:
        pass


def norm_title(title: str) -> str:
    t = re.sub(r"\(\d+\)", "", title)          # unread counters
    t = re.sub(r"\d+", "#", t)                  # numbers
    return re.sub(r"\s+", " ", t).strip().lower()[:120]


# ---------- activity ----------

def rule_activity(mode: Mode, cls: str, title: str, browsers: list[str] = ()) -> tuple[str, str] | None:
    text = f"{cls}|{title}"
    if p := mode.matches(mode.off_task, text):
        return "off", f"matches off_task rule '{p}'"
    if p := mode.matches(mode.on_task, text):
        return "on", f"matches on_task rule '{p}'"
    is_browser = any(b.lower() in cls.lower() for b in browsers)
    is_mode_app = cls and any(cls.lower() == a.lower() or cls.lower() in a.lower() for a in mode.apps)
    if is_mode_app and not is_browser:
        return "on", "mode app"
    # a browser is judged by its tab title, never by being a mode app
    if mode.unknown == "neutral":
        return "neutral", "unknown app (mode treats unknown as neutral)"
    if mode.unknown == "off":
        return "off", "unknown app (mode treats unknown as off task)"
    return None


async def _ask(system: str, user: str) -> dict | None:
    async with _sem:
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", "--no-session-persistence", "--model", MODEL,
                "--output-format", "json", "--tools", "", "--system-prompt", system,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL)
            out, _ = await asyncio.wait_for(proc.communicate(user.encode()), timeout=40)
            res = json.loads(out)
            if res.get("is_error"):
                return None
            txt = res.get("result", "")
            m = re.search(r"\{.*\}", txt, re.S)
            return json.loads(m.group(0)) if m else None
        except (asyncio.TimeoutError, json.JSONDecodeError, OSError, ValueError):
            return None


ACTIVITY_SYS = (
    "You classify whether a desktop window is on task for a focus mode. "
    "Answer ONLY compact JSON: {\"verdict\":\"on\"|\"off\"|\"neutral\",\"reason\":\"<=12 words\"}. "
    "neutral = system/utility windows or genuinely ambiguous."
)


async def llm_activity(mode: Mode, cls: str, title: str) -> tuple[str, str]:
    key = f"a|{mode.id}|{cls}|{norm_title(title)}"
    if key in _cache:
        c = _cache[key]
        return c["verdict"], c["reason"] + " (cached)"
    user = json.dumps({"mode": mode.label, "mode_description": mode.description,
                       "mode_apps": mode.apps, "window_class": cls, "window_title": title})
    res = await _ask(ACTIVITY_SYS, user)
    if not res or res.get("verdict") not in ("on", "off", "neutral"):
        return "neutral", "classifier unavailable"
    _cache[key] = {"verdict": res["verdict"], "reason": res.get("reason", ""), "ts": time.time()}
    _save_cache()
    return res["verdict"], res.get("reason", "")


# ---------- notifications ----------

def rule_notification(mode: Mode, app: str, desktop_entry: str, summary: str, body: str,
                      urgency: int) -> tuple[str, str] | None:
    n: Notifications = mode.notifications
    if urgency >= 2:
        return "pass", "critical urgency"
    ident = f"{app}|{desktop_entry}"
    if p := mode.matches(n.hold_from, ident):
        return "hold", f"hold_from '{p}'"
    if p := mode.matches(n.allow_from, ident):
        return "pass", f"allow_from '{p}'"
    if p := mode.matches(n.pass_keywords, f"{summary}\n{body}"):
        return "pass", f"keyword '{p}'"
    if n.default in ("pass", "hold"):
        return n.default, f"mode default '{n.default}'"
    return None


NOTIF_SYS = (
    "You decide whether a desktop notification should interrupt someone in a focus mode now, "
    "or be held until the mode ends. Answer ONLY compact JSON: "
    "{\"action\":\"pass\"|\"hold\",\"reason\":\"<=12 words\"}. Pass only if time-sensitive and relevant to the mode "
    "or clearly important (people waiting, failures, calendar in the next hour)."
)


async def llm_notification(mode: Mode, app: str, summary: str, body: str) -> tuple[str, str]:
    key = f"n|{mode.id}|{app}|{norm_title(summary)}"
    if key in _cache:
        c = _cache[key]
        return c["action"], c["reason"] + " (cached)"
    user = json.dumps({"mode": mode.label, "mode_description": mode.description,
                       "app": app, "summary": summary, "body": body[:400]})
    res = await _ask(NOTIF_SYS, user)
    if not res or res.get("action") not in ("pass", "hold"):
        return "pass", "classifier unavailable (fail open)"
    _cache[key] = {"action": res["action"], "reason": res.get("reason", ""), "ts": time.time()}
    _save_cache()
    return res["action"], res.get("reason", "")
