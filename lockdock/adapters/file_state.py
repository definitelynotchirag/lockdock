"""state.json for the dock, written atomically."""
from __future__ import annotations

import json
import os
from pathlib import Path


class AtomicJsonStatePublisher:
    """StatePublisher: write to a temp file, then rename over state.json (the dock watches it)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def publish(self, snapshot: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(snapshot, ensure_ascii=False))
        os.replace(tmp, self.path)
