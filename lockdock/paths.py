"""Where lockdock keeps its config, state and runtime files (XDG)."""
from __future__ import annotations

import os
from pathlib import Path

# LOCKDOCK_INSTANCE=<name> runs a second, fully isolated daemon+dock (dev/testing).
INSTANCE = os.environ.get("LOCKDOCK_INSTANCE", "")
_DIR = "lockdock" + (f"-{INSTANCE}" if INSTANCE else "")

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / _DIR
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / _DIR
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / _DIR

MODES_FILE = CONFIG_DIR / "modes.json"
THEME_FILE = CONFIG_DIR / "theme.json"
STATE_FILE = RUNTIME_DIR / "state.json"
SOCKET_FILE = RUNTIME_DIR / "sock"
EVENTS_LOG = STATE_DIR / "events.jsonl"
CACHE_FILE = STATE_DIR / "classify-cache.json"


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, STATE_DIR, RUNTIME_DIR):
        d.mkdir(parents=True, exist_ok=True)
