import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "lockdock"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "lockdock"
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "lockdock"

MODES_FILE = CONFIG_DIR / "modes.json"
STATE_FILE = RUNTIME_DIR / "state.json"
SOCKET_FILE = RUNTIME_DIR / "sock"
EVENTS_LOG = STATE_DIR / "events.jsonl"
CACHE_FILE = STATE_DIR / "classify-cache.json"


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, STATE_DIR, RUNTIME_DIR):
        d.mkdir(parents=True, exist_ok=True)
