"""Client side of the daemon's control socket."""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any

from ..paths import SOCKET_FILE


def call(cmd: str, arg: str | None = None, path: Path = SOCKET_FILE) -> Any:
    """Send one command and return its result; exits if the daemon is down or errors."""
    s = socket.socket(socket.AF_UNIX)
    try:
        s.connect(str(path))
    except OSError:
        sys.exit("lockdock daemon is not running (start with: lockdock daemon)")
    s.sendall((json.dumps({"cmd": cmd, "arg": arg}) + "\n").encode())
    data = b""
    while chunk := s.recv(65536):
        data += chunk
    res = json.loads(data)
    if not res.get("ok"):
        sys.exit(res.get("error"))
    return res["result"]
