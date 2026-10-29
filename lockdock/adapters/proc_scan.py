"""ProcessScanner backed by /proc (Linux, stdlib only)."""
from __future__ import annotations

import os
from pathlib import Path

from ..core.models import ProcessInfo


def _stat(pid: int, proc: Path) -> tuple[int, float] | None:
    """(ppid, cpu seconds) from /proc/<pid>/stat; the comm field may contain spaces and parens."""
    try:
        raw = (proc / str(pid) / "stat").read_text()
    except OSError:
        return None
    fields = raw[raw.rfind(")") + 2:].split()
    # fields[0] is state (field 3); ppid is field 4, utime 14, stime 15
    try:
        return int(fields[1]), (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")
    except (IndexError, ValueError):
        return None


def ancestor_pids(pid: int, proc: Path = Path("/proc"), limit: int = 12) -> list[int]:
    """`pid` and its parents, nearest first (used by `lockdock agent-event` to identify its agent)."""
    out: list[int] = []
    while pid > 1 and len(out) < limit:
        out.append(pid)
        st = _stat(pid, proc)
        if not st:
            break
        pid = st[0]
    return out


class ProcScanner:
    """Lists the current user's processes from /proc."""

    def __init__(self, proc: Path = Path("/proc"), uid: int | None = None) -> None:
        self.proc = proc
        self.uid = os.getuid() if uid is None else uid

    def scan(self) -> list[ProcessInfo]:
        out: list[ProcessInfo] = []
        try:
            entries = [e for e in os.listdir(self.proc) if e.isdigit()]
        except OSError:
            return out
        for e in entries:
            d = self.proc / e
            try:
                if d.stat().st_uid != self.uid:
                    continue
                argv = (d / "cmdline").read_bytes().split(b"\0")
            except OSError:
                continue
            st = _stat(int(e), self.proc)
            if not st or not argv or not argv[0]:
                continue  # kernel threads have an empty cmdline
            try:
                cwd = os.readlink(d / "cwd")
            except OSError:
                cwd = ""
            cmd = tuple(a.decode(errors="replace") for a in (argv[:-1] if argv[-1] == b"" else argv))
            out.append(ProcessInfo(pid=int(e), ppid=st[0], cmdline=cmd, cwd=cwd, cpu_s=st[1]))
        return out
