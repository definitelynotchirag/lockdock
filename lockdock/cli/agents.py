"""CLI verbs of the agent inbox: agent-event (hooks), agents (list / install-hooks), agent focus."""
from __future__ import annotations

import difflib
import json
import os
import select
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from ..core.agent_hooks import merge_claude_settings, merge_codex_config
from .client import call, try_call

CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
CODEX_CONFIG = Path.home() / ".codex" / "config.toml"
BACKUP_SUFFIX = ".bak-lockdock"
STDIN_WAIT_S = 1.0


def read_payload(rest: list[str]) -> dict:
    """Hook JSON: a JSON argv argument (Codex notify) or stdin (Claude Code hooks). {} if none."""
    for a in rest:
        if a.lstrip().startswith("{"):
            try:
                v = json.loads(a)
                return v if isinstance(v, dict) else {}
            except json.JSONDecodeError:
                return {}
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        ready, _, _ = select.select([sys.stdin], [], [], STDIN_WAIT_S)
        raw = sys.stdin.read() if ready else ""
        v = json.loads(raw) if raw.strip() else {}
    except (OSError, ValueError):
        return {}
    return v if isinstance(v, dict) else {}


def agent_event(rest: list[str]) -> None:
    """`lockdock agent-event <kind> <state> [json]`. Silent and always exit 0: it runs inside agent hooks."""
    if len(rest) < 2:
        return
    from ..adapters.proc_scan import ancestor_pids
    payload = read_payload(rest[2:])
    try_call("agent_event", {"kind": rest[0], "state": rest[1], "payload": payload,
                             "pids": ancestor_pids(os.getppid())})


def _age(ms: int) -> str:
    s = max(0, int(time.time() - ms / 1000))
    return f"{s}s" if s < 60 else f"{s // 60}m" if s < 3600 else f"{s // 3600}h"


def list_agents(rest: list[str]) -> None:
    agents: list[dict[str, Any]] = call("agents")
    if "--json" in rest:
        print(json.dumps(agents, indent=2, ensure_ascii=False))
        return
    if not agents:
        print("no agents running")
        return
    print(f"{'ID':<22} {'KIND':<8} {'STATE':<12} {'AGE':>4}  {'LABEL':<18} {'WINDOW':<16} MESSAGE / CWD")
    for a in agents:
        tail = a.get("last_message") or a.get("cwd") or ""
        print(f"{a['id']:<22} {a['kind']:<8} {a['state']:<12} {_age(a['since_ms']):>4}  {a['label'][:18]:<18} "
              f"{a.get('window_address') or '-':<16} {tail[:60]}")


def _write(path: Path, old: str, new: str, dry: bool) -> None:
    diff = "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        str(path), f"{path} (lockdock)"))
    if dry:
        print(diff or f"{path}: no change")
        return
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
        print(f"backed up {path} -> {backup}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-lockdock")
    tmp.write_text(new)
    os.replace(tmp, path)


def install_claude(path: Path, dry: bool, exe: str = "lockdock") -> list[str]:
    """Merge our hooks into a Claude Code settings.json. Returns the events added."""
    old = path.read_text() if path.exists() else ""
    settings = json.loads(old) if old.strip() else {}
    if not isinstance(settings, dict):
        raise ValueError(f"{path} is not a JSON object")
    new, added = merge_claude_settings(settings, exe)
    if added:
        _write(path, old, json.dumps(new, indent=2, ensure_ascii=False) + "\n", dry)
    return added


def install_codex(path: Path, dry: bool) -> str:
    """Add our notify line to a Codex config.toml. Returns added / present / other."""
    old = path.read_text() if path.exists() else ""
    new, status = merge_codex_config(old)
    if status == "added":
        _write(path, old, new, dry)
    return status


def install_hooks(rest: list[str]) -> None:
    dry = "--dry-run" in rest
    claude, codex = "--claude" in rest, "--codex" in rest
    if not claude and not codex:
        claude = codex = True
    if claude:
        try:
            added = install_claude(CLAUDE_SETTINGS, dry)
        except (ValueError, OSError) as e:
            sys.exit(f"claude: {e}")
        print(f"claude: {'would add' if dry else 'added'} {', '.join(added)}" if added
              else "claude: hooks already installed")
    if codex:
        status = install_codex(CODEX_CONFIG, dry)
        print({"added": f"codex: {'would add' if dry else 'added'} notify",
               "present": "codex: notify already installed",
               "other": "codex: config.toml already has a different notify program; left it alone "
                        "(Codex runs only one)"}[status])


def main(cmd: str, rest: list[str]) -> None:
    """Dispatch `agent-event`, `agents [...]` and `agent <sub> ...`."""
    if cmd == "agent-event":
        agent_event(rest)
    elif cmd == "agents" and rest[:1] == ["install-hooks"]:
        install_hooks(rest[1:])
    elif cmd == "agents":
        list_agents(rest)
    elif cmd == "agent" and len(rest) >= 2 and rest[0] == "focus":
        print(call("agent_focus", rest[1]))
    else:
        sys.exit("usage: lockdock agent focus <id>")
