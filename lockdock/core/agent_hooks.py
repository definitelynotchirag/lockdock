"""Pure merge logic for `lockdock agents install-hooks` (no file I/O here).

Claude Code: entries appended to `~/.claude/settings.json` `hooks`, never
replacing anything. Codex: a top-level `notify = [...]` line in
`~/.codex/config.toml` when none is set.
"""
from __future__ import annotations

import copy
import re
from typing import Any

# Claude Code hook event -> agent state
CLAUDE_EVENTS: dict[str, str] = {
    "Notification": "needs_input",
    "UserPromptSubmit": "working",
    "PreToolUse": "working",
    "Stop": "done",
    "SessionEnd": "done",
}
# events whose entries take a tool-name matcher
_MATCHER_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest"}
HOOK_TIMEOUT_S = 5
CODEX_NOTIFY = 'notify = ["lockdock", "agent-event", "codex", "needs_input"]'


def claude_command(state: str, exe: str = "lockdock") -> str:
    return f"{exe} agent-event claude {state}"


def _has_command(entries: Any, command: str) -> bool:
    for entry in entries if isinstance(entries, list) else []:
        for h in (entry.get("hooks") or []) if isinstance(entry, dict) else []:
            if isinstance(h, dict) and h.get("command") == command:
                return True
    return False


def merge_claude_settings(settings: dict, exe: str = "lockdock") -> tuple[dict, list[str]]:
    """Return (new settings, events added). Existing hooks are kept as they are;
    an event is skipped when an identical command is already registered for it."""
    out = copy.deepcopy(settings)
    hooks = out.get("hooks")
    if hooks is None:
        hooks = out["hooks"] = {}
    if not isinstance(hooks, dict):
        raise ValueError("settings.json 'hooks' is not an object; refusing to touch it")
    added = []
    for event, state in CLAUDE_EVENTS.items():
        cmd = claude_command(state, exe)
        entries = hooks.get(event)
        if entries is not None and not isinstance(entries, list):
            raise ValueError(f"settings.json hooks.{event} is not a list; refusing to touch it")
        if _has_command(entries, cmd):
            continue
        entry: dict[str, Any] = {"hooks": [{"type": "command", "command": cmd, "timeout": HOOK_TIMEOUT_S}]}
        if event in _MATCHER_EVENTS:
            entry = {"matcher": "*", **entry}
        hooks[event] = [*(entries or []), entry]
        added.append(event)
    return out, added


_TABLE = re.compile(r"^\s*\[")
_NOTIFY = re.compile(r"^\s*notify\s*=")


def merge_codex_config(text: str) -> tuple[str, str]:
    """Return (new text, status). status: `added`, `present` (ours), or `other` (a different notify
    is set; Codex allows one, so we leave it)."""
    lines = text.splitlines(keepends=True)
    first_table = next((i for i, line in enumerate(lines) if _TABLE.match(line)), len(lines))
    for line in lines[:first_table]:
        if _NOTIFY.match(line):
            return text, ("present" if "agent-event" in line and "lockdock" in line else "other")
    block = ["# lockdock agent inbox: mark the agent as waiting for you when a turn completes\n",
             CODEX_NOTIFY + "\n"]
    if first_table < len(lines):
        block.append("\n")
    head = lines[:first_table]
    if head and not head[-1].endswith("\n"):
        head[-1] += "\n"
    return "".join(head + block + lines[first_table:]), "added"
