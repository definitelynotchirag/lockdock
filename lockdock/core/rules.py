"""Regex rule helpers shared by activity and notification rules."""
from __future__ import annotations

import re


def matches(patterns: list[str], text: str) -> str | None:
    """The first pattern that matches `text` (case-insensitive), or None.

    An invalid regex falls back to a plain substring test.
    """
    for p in patterns:
        try:
            if re.search(p, text, re.I):
                return p
        except re.error:
            if p.lower() in text.lower():
                return p
    return None


def hit(pattern: str, text: str) -> str:
    """What `pattern` matched in `text` (case-insensitive), for a human-readable reason; the
    pattern itself when it matched nothing visible (e.g. `.*` matching "") or is invalid."""
    try:
        m = re.search(pattern, text, re.I)
    except re.error:
        return pattern
    found = (m.group(0) if m else "").strip(" |").split("|")[0].strip()
    return found[:40] if found else pattern


def norm_title(title: str) -> str:
    """Normalise a title for caching: drop unread counters and digits, collapse spaces."""
    t = re.sub(r"\(\d+\)", "", title)          # unread counters
    t = re.sub(r"\d+", "#", t)                  # numbers
    return re.sub(r"\s+", " ", t).strip().lower()[:120]
