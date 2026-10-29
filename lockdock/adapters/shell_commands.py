"""Running on_enter / on_exit commands."""
from __future__ import annotations

import subprocess


class SubprocessCommandRunner:
    """CommandRunner: fire-and-forget `sh -c cmd`."""

    def run(self, cmd: str) -> None:
        subprocess.Popen(cmd, shell=True)
