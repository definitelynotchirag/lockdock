"""The agent inbox: which coding agents are running and which of them waits for the user.

Two signal sources are merged by `AgentRegistry`:

- periodic process scans (presence, pid, cwd, kind; a CPU-based working/idle
  guess for agents that never sent a hook event), and
- hook events from the agents themselves (`lockdock agent-event <kind> <state>`),
  which always win over a scan guess.
"""
from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from .events import EventSink
from .models import AgentInfo, AgentKind, AgentState, ProcessInfo
from .ports import Clock, NotificationSink

DEFAULT_KINDS: tuple[AgentKind, ...] = (
    # T3 Code runs agents as children of its server; listed first so it wins over plain claude/codex.
    AgentKind("t3", "Ⓣ", patterns=("claude", "codex"), ancestors=("t3code", "t3-code"),
              exclude=("-p", "--print"), label_arg="--add-dir", hook_kind="claude"),
    AgentKind("claude", "✻", patterns=("claude", "claude-code", "/claude-code/cli"),
              exclude=("-p", "--print", "mcp", "update", "doctor", "config")),
    AgentKind("codex", "❂", patterns=("codex", "codex\\.js"),
              exclude=("exec", "app-server", "mcp", "mcp-server", "login", "proto")),
    AgentKind("opencode", "◇", patterns=("opencode",), exclude=("serve", "run")),
    AgentKind("aider", "▲", patterns=("aider",)),
    AgentKind("gemini", "✦", patterns=("gemini",), exclude=("-p", "--prompt")),
    AgentKind("cursor-agent", "⬢", patterns=("cursor-agent",), exclude=("-p", "--print")),
)

INTERPRETER = re.compile(r"(node|nodejs|bun|deno|python[0-9.]*|uv|uvx|pipx)", re.I)
UNSEEN_DROP_S = 10.0          # a scanned agent the scanner stopped seeing is dropped after this
DONE_KEEP_S = 600.0           # ... unless it is done: done agents stay this long
HOOK_ONLY_TTL_S = 1800.0      # a hook-only agent (no process found) without events is dropped after this
WINDOW_RETRY_S = 30.0         # retry a failed window lookup after this
ACTIVE_CPU_RATIO = 0.03       # CPU seconds per wall second above which an un-hooked agent counts as working
QUIET_IDLE_S = 9.0            # ... and below which it must stay this long to fall back to idle
MESSAGE_MAX = 300
STATE_ORDER = {AgentState.NEEDS_INPUT: 0, AgentState.WORKING: 1, AgentState.IDLE: 2, AgentState.DONE: 3}


# ---------- kind detection ----------
def _tup(v: Any) -> tuple[str, ...]:
    if v is None:
        return ()
    if isinstance(v, str):
        return (v,)
    if isinstance(v, (list, tuple)) and all(isinstance(x, str) for x in v):
        return tuple(v)
    raise ValueError(f"expected a string or a list of strings, got {v!r}")


def merge_kinds(defaults: Iterable[AgentKind], raw: list[dict] | None) -> list[AgentKind]:
    """modes.json `agents.kinds` merged over `defaults`.

    An entry whose `name` matches a default overrides the given fields of it
    (`"enabled": false` removes it); a new name is added before the defaults so
    it can shadow their generic patterns. Raises ValueError on bad input.
    """
    kinds = {k.name: k for k in defaults}
    order = list(kinds)
    new: list[str] = []
    for entry in raw or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ValueError(f"agents.kinds entry needs a 'name': {entry!r}")
        name = entry["name"]
        if entry.get("enabled", True) is False:
            kinds.pop(name, None)
            continue
        base = kinds.get(name) or AgentKind(name)
        fields: dict[str, Any] = {}
        for key in ("patterns", "ancestors", "exclude"):
            if key in entry:
                fields[key] = _tup(entry[key])
                for p in fields[key]:
                    try:
                        re.compile(p)
                    except re.error as e:   # not a ValueError; the config loader only catches those
                        raise ValueError(f"agents.kinds {name}.{key}: bad regex {p!r}: {e}") from e
        for key in ("glyph", "label_arg", "hook_kind"):
            if key in entry:
                fields[key] = str(entry[key])
        kinds[name] = replace(base, **fields)
        if name not in order and name not in new:
            new.append(name)
    return [kinds[n] for n in new + order if n in kinds]


def program_names(cmdline: tuple[str, ...]) -> list[str]:
    """argv[0], plus the script an interpreter (node, python, bun, ...) runs. Full paths."""
    if not cmdline:
        return []
    names = [cmdline[0]]
    if INTERPRETER.fullmatch(os.path.basename(cmdline[0])):
        script = next((a for a in cmdline[1:] if not a.startswith("-")), None)
        if script:
            names.append(script)
    return names


def _matches(patterns: tuple[str, ...], paths: list[str]) -> bool:
    for p in patterns:
        for path in paths:
            if "/" in p:
                if re.search(p, path, re.I):
                    return True
            elif re.fullmatch(p, os.path.basename(path), re.I):
                return True
    return False


def ancestors(pid: int, procs: Mapping[int, ProcessInfo], limit: int = 32) -> list[ProcessInfo]:
    """The parent chain of `pid` (nearest first), as far as `procs` knows it."""
    out: list[ProcessInfo] = []
    p = procs.get(pid)
    seen = {pid}
    while p and len(out) < limit:
        p = procs.get(p.ppid)
        if not p or p.pid in seen:
            break
        seen.add(p.pid)
        out.append(p)
    return out


def classify(p: ProcessInfo, procs: Mapping[int, ProcessInfo], kinds: Iterable[AgentKind]) -> AgentKind | None:
    """The first kind whose patterns (and ancestor / exclude rules) fit process `p`."""
    names = program_names(p.cmdline)
    if not names:
        return None
    args = p.cmdline[1:]
    for k in kinds:
        if not _matches(k.patterns, names):
            continue
        if any(re.fullmatch(x, a) for x in k.exclude for a in args):
            continue
        if k.ancestors and not any(_matches(k.ancestors, program_names(a.cmdline))
                                   for a in ancestors(p.pid, procs)):
            continue
        return k
    return None


def detect(procs: Mapping[int, ProcessInfo], kinds: Iterable[AgentKind]) -> list[tuple[ProcessInfo, AgentKind]]:
    """Every agent process, skipping ones whose ancestor is itself an agent (wrappers, nested runs)."""
    kinds = list(kinds)
    found = {pid: k for pid, p in procs.items() if (k := classify(p, procs, kinds))}
    return [(procs[pid], k) for pid, k in sorted(found.items())
            if not any(a.pid in found for a in ancestors(pid, procs))]


def arg_value(cmdline: tuple[str, ...], flag: str) -> str:
    """The value of `--flag value` or `--flag=value` (first occurrence), or ''."""
    for i, a in enumerate(cmdline):
        if a == flag and i + 1 < len(cmdline):
            return cmdline[i + 1]
        if a.startswith(flag + "="):
            return a[len(flag) + 1:]
    return ""


def window_for(pid: int, procs: Mapping[int, ProcessInfo], window_for_pid: Callable[[int], str | None]) -> str | None:
    """Walk the ppid chain from `pid` until a process that owns a window (terminal, T3 Code)."""
    for p in [procs[pid]] + ancestors(pid, procs) if pid in procs else []:
        if addr := window_for_pid(p.pid):
            return addr
    return None


# ---------- hook events ----------
@dataclass(frozen=True)
class AgentEvent:
    """A state change reported by an agent hook (`lockdock agent-event`)."""

    kind: str
    state: AgentState
    session_id: str = ""
    cwd: str = ""
    message: str = ""
    hook_event: str = ""
    pids: tuple[int, ...] = ()   # the hook process's ancestors, nearest first


def parse_hook_event(kind: str, state: str, payload: Mapping[str, Any] | None,
                     pids: Iterable[int] = ()) -> AgentEvent:
    """Build an AgentEvent from a hook's JSON (Claude Code stdin, Codex notify argv). Raises ValueError."""
    d = dict(payload or {})

    def get(*keys: str) -> str:
        for k in keys:
            v = d.get(k)
            if isinstance(v, str) and v:
                return v
        return ""

    msg = get("message", "last_assistant_message", "last-assistant-message", "prompt")
    if not msg and (tool := get("tool_name")):
        msg = f"running {tool}"
    return AgentEvent(kind=kind, state=AgentState(state),
                      session_id=get("session_id", "thread-id", "thread_id", "session-id"),
                      cwd=os.path.normpath(get("cwd")) if get("cwd") else "",
                      message=" ".join(msg.split())[:MESSAGE_MAX],
                      hook_event=get("hook_event_name", "type"),
                      pids=tuple(int(p) for p in pids))


# ---------- the registry ----------
class AgentRegistry:
    """Merges process scans and hook events into the list of agents the dock shows.

    Rules: a hook event wins over a scan guess (an agent that ever sent one is
    never guessed again); a scanned agent unseen for 10 s is dropped, except
    `done` agents, kept 10 min; `needs_input` is sticky until a working/done
    event or until the user focuses the agent's window. Entering needs_input
    sends one desktop notification.
    """

    def __init__(self, clock: Clock, on_change: Callable[[], None],
                 window_for_pid: Callable[[int], str | None] = lambda pid: None,
                 kinds: Iterable[AgentKind] = DEFAULT_KINDS, sink: NotificationSink | None = None,
                 events: EventSink | None = None) -> None:
        self.clock = clock
        self.on_change = on_change
        self.window_for_pid = window_for_pid
        self.kinds = list(kinds)
        self.sink = sink
        self.events = events
        self.agents: dict[str, AgentInfo] = {}
        self._seen: dict[str, float] = {}          # scanned agents: last time the scanner saw them
        self._last_event: dict[str, float] = {}    # hooked agents: last hook event time
        self._hook_pids: dict[str, tuple[int, ...]] = {}  # hook-only agents: pids their events came from
        self._cpu: dict[str, tuple[float, float]] = {}    # id -> (cpu_s, at)
        self._active_at: dict[str, float] = {}
        self._win_miss: dict[int, float] = {}
        self.focused: str | None = None

    # ---------- queries ----------
    def snapshot(self) -> list[dict]:
        """needs_input first, then working, idle, done; stable within a state."""
        return [a.to_dict() for a in sorted(self.agents.values(),
                                            key=lambda a: (STATE_ORDER[a.state], a.label, a.id))]

    def get(self, agent_id: str) -> AgentInfo | None:
        """By exact id, else by a unique id prefix or label."""
        if agent_id in self.agents:
            return self.agents[agent_id]
        hits = [a for a in self.agents.values() if a.id.startswith(agent_id) or a.label == agent_id]
        return hits[0] if len(hits) == 1 else None

    # ---------- inputs ----------
    def on_scan(self, scan: Iterable[ProcessInfo]) -> None:
        """One ProcessScanner result: add, update and expire agents."""
        now = self.clock.now()
        procs = {p.pid: p for p in scan}
        changed = False
        for p, kind in detect(procs, self.kinds):
            aid = f"{kind.name}:{p.pid}"
            a = self.agents.get(aid)
            if a is None:
                a = self._new_scanned(aid, p, kind, procs, now)
                changed = True
            self._seen[aid] = now
            if p.cwd and p.cwd != a.cwd:
                a.cwd = p.cwd
                changed = True
            if a.window_address is None and now >= self._win_miss.get(p.pid, 0):
                a.window_address = window_for(p.pid, procs, self.window_for_pid)
                if a.window_address:
                    changed = True
                else:
                    self._win_miss[p.pid] = now + WINDOW_RETRY_S
            changed |= self._guess(a, p, now)
        changed |= self._expire(now)
        if changed:
            self.on_change()

    def on_event(self, ev: AgentEvent) -> AgentInfo:
        """A hook event: update the matching agent, or create a hook-only one."""
        now = self.clock.now()
        a = self._match(ev)
        if a is None:
            aid = f"{ev.kind}:{ev.session_id or ev.cwd or 'unknown'}"
            kind = next((k for k in self.kinds if k.name == ev.kind), AgentKind(ev.kind))
            a = AgentInfo(id=aid, kind=ev.kind, label=os.path.basename(ev.cwd) or ev.kind,
                          state=ev.state, since_ms=int(now * 1000), cwd=ev.cwd, session_id=ev.session_id,
                          glyph=kind.glyph, last_message=ev.message)
            self.agents[aid] = a
            self._hook_pids[aid] = ev.pids
            self._last_event[aid] = now
            self._log(a)
            if a.state is AgentState.NEEDS_INPUT:
                self._notify(a)
            self.on_change()
            return a
        self._last_event[a.id] = now
        if a.pid is None:
            self._hook_pids[a.id] = ev.pids or self._hook_pids.get(a.id, ())
        if ev.session_id and not a.session_id:
            a.session_id = ev.session_id
        self._set_state(a, ev.state, ev.message, now)
        return a

    def on_focus(self, address: str | None) -> None:
        """The user focused a window: a needs_input agent living in it goes back to working."""
        self.focused = address
        if not address:
            return
        now = self.clock.now()
        for a in self.agents.values():
            if a.window_address == address and a.state is AgentState.NEEDS_INPUT:
                self._set_state(a, AgentState.WORKING, "", now)

    # ---------- internals ----------
    def _new_scanned(self, aid: str, p: ProcessInfo, kind: AgentKind, procs: Mapping[int, ProcessInfo],
                     now: float) -> AgentInfo:
        label_src = arg_value(p.cmdline, kind.label_arg) if kind.label_arg else ""
        label = os.path.basename(os.path.normpath(label_src or p.cwd)) or kind.name
        session = arg_value(p.cmdline, "--session-id") or arg_value(p.cmdline, "--resume")
        a = AgentInfo(id=aid, kind=kind.name, label=label, since_ms=int(now * 1000), pid=p.pid,
                      cwd=p.cwd, session_id=session, glyph=kind.glyph)
        self.agents[aid] = a
        # adopt a hook-only entry that turns out to be this process
        for other in list(self.agents.values()):
            if other.pid is not None or other is a:
                continue
            same = ((session and other.session_id == session) or p.pid in self._hook_pids.get(other.id, ())
                    or (not other.session_id and other.cwd == p.cwd and other.kind == kind.event_kind))
            if same:
                a.state, a.since_ms, a.last_message = other.state, other.since_ms, other.last_message
                a.session_id = a.session_id or other.session_id
                self._last_event[aid] = self._last_event.pop(other.id, now)
                self._drop(other.id)
                break
        return a

    def _guess(self, a: AgentInfo, p: ProcessInfo, now: float) -> bool:
        """CPU-based working/idle guess, only for agents that never sent a hook event."""
        prev = self._cpu.get(a.id)
        self._cpu[a.id] = (p.cpu_s, now)
        if a.id in self._last_event or prev is None or now <= prev[1]:
            return False
        if (p.cpu_s - prev[0]) / (now - prev[1]) >= ACTIVE_CPU_RATIO:
            self._active_at[a.id] = now
            want = AgentState.WORKING
        elif now - self._active_at.get(a.id, 0) >= QUIET_IDLE_S:
            want = AgentState.IDLE
        else:
            return False
        if a.state in (AgentState.IDLE, AgentState.WORKING) and a.state is not want:
            a.state, a.since_ms = want, int(now * 1000)
            return True
        return False

    def _expire(self, now: float) -> bool:
        gone = []
        for aid, a in self.agents.items():
            age = now - a.since_ms / 1000
            if a.pid is not None:
                unseen = now - self._seen.get(aid, now) >= UNSEEN_DROP_S
                if unseen and not (a.state is AgentState.DONE and age < DONE_KEEP_S):
                    gone.append(aid)
            elif ((a.state is AgentState.DONE and age >= DONE_KEEP_S)
                  or now - self._last_event.get(aid, now) >= HOOK_ONLY_TTL_S):
                gone.append(aid)
        for aid in gone:
            self._drop(aid)
        return bool(gone)

    def _drop(self, aid: str) -> None:
        a = self.agents.pop(aid, None)
        for d in (self._seen, self._last_event, self._hook_pids, self._cpu, self._active_at):
            d.pop(aid, None)
        if a and a.pid is not None:
            self._win_miss.pop(a.pid, None)

    def _match(self, ev: AgentEvent) -> AgentInfo | None:
        agents = list(self.agents.values())
        if ev.session_id:
            for a in agents:
                if a.session_id == ev.session_id:
                    return a
        for pid in ev.pids:
            for a in agents:
                if a.pid == pid:
                    return a
        kinds = {k.name: k.event_kind for k in self.kinds}
        same = [a for a in agents if ev.cwd and a.cwd == ev.cwd and kinds.get(a.kind, a.kind) == ev.kind
                and not (ev.session_id and a.session_id)]
        return min(same, key=lambda a: a.pid or 0) if same else None

    def _set_state(self, a: AgentInfo, state: AgentState, message: str, now: float) -> None:
        if state is a.state:
            # debounce (PreToolUse fires per tool call): only a new needs_input message is worth a publish
            if message and message != a.last_message:
                a.last_message = message
                if state is AgentState.NEEDS_INPUT:
                    self.on_change()
            return
        a.state, a.since_ms = state, int(now * 1000)
        if message:
            a.last_message = message
        self._log(a)
        if state is AgentState.NEEDS_INPUT:
            self._notify(a)
        self.on_change()

    def _notify(self, a: AgentInfo) -> None:
        if self.sink:
            self.sink.send("lockdock", f"{a.kind} needs you · {a.label}", a.last_message or a.cwd, urgency=1)

    def _log(self, a: AgentInfo) -> None:
        if self.events:
            self.events.log("agent", id=a.id, state=str(a.state), label=a.label)
