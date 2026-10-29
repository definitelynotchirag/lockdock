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


def norm_title(title: str) -> str:
    """Normalise a title for caching: drop unread counters and digits, collapse spaces."""
    t = re.sub(r"\(\d+\)", "", title)          # unread counters
    t = re.sub(r"\d+", "#", t)                  # numbers
    return re.sub(r"\s+", " ", t).strip().lower()[:120]
