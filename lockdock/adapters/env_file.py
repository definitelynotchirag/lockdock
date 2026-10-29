"""Secrets from a dotenv-style file (~/.config/lockdock/.env): KEY=VALUE lines, no shell."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def load_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines. `#` starts a comment line, an optional `export ` prefix is dropped,
    a value wrapped in matching single or double quotes is unwrapped (no escapes, no expansion).
    A missing or unreadable file is an empty dict."""
    try:
        text = path.read_text()
    except OSError:
        return {}
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()   # trailing comment on an unquoted value
        if key:
            out[key] = value
    return out


def lookup(name: str, path: Path, environ: Mapping[str, str] | None = None) -> str:
    """`name` from the process environment first, then from the env file; "" when neither has it."""
    env = os.environ if environ is None else environ
    return env.get(name) or load_env_file(path).get(name, "")
