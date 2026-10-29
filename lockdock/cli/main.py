"""lockdock CLI.

  lockdock daemon            run the daemon (foreground)
  lockdock shell             run the Quickshell dock (foreground)
  lockdock mode <id>         switch mode (press again to shorten the exit countdown)
  lockdock cancel            cancel a pending switch
  lockdock status [--json]   current mode, activity verdict, held notifications
  lockdock modes             list modes from modes.json
  lockdock url               last browser URL and bridge health (browser extension)
  lockdock held              list held notifications
  lockdock release           re-deliver held notifications now
  lockdock reload            reload modes.json (also happens automatically)
  lockdock log [-n N]        tail events.jsonl (what was classified and why)
  lockdock config            print the modes.json path
  lockdock agents [--json]   running coding agents and whether they need you
  lockdock agent focus <id>  focus an agent's window
  lockdock agents install-hooks [--claude] [--codex] [--dry-run]
                             report agent state from Claude Code / Codex hooks
  lockdock agent-event <kind> <state> [json]
                             (used by hooks) report an agent's state; JSON on stdin
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ..paths import EVENTS_LOG, MODES_FILE, STATE_FILE
from .client import call

ROOT = Path(__file__).resolve().parents[2]
USAGE = (__doc__ or "").strip()


def _status(rest: list[str]) -> None:
    st = call("status")
    if "--json" in rest:
        print(json.dumps(st, indent=2))
        return
    print(f"mode: {st['mode']}")
    if st.get("pending"):
        print(f"pending: -> {st['pending']['mode']}")
    a = st.get("activity") or {}
    print(f"activity: {a.get('verdict')}  {a.get('app')}: {a.get('title', '')[:60]}\n  why: {a.get('reason')}")
    print(f"held notifications: {st.get('held_count', 0)}")


def _url(b: dict) -> None:
    if not isinstance(b, dict):
        print(b)
        return
    if not b.get("enabled"):
        state = "disabled"
    else:
        state = f"listening on 127.0.0.1:{b.get('port')}" if b.get("listening") else "enabled, NOT listening"
    print(f"bridge: {state}")
    seen = f"last seen {b['age_s']}s ago" if b.get("age_s") is not None else "never seen"
    print(f"connected: {'yes' if b.get('connected') else 'no'}  ({seen})")
    print(f"url: {b.get('url') or '(none)'}")


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return
    cmd, rest = args[0], args[1:]
    if cmd in ("agent-event", "agents", "agent"):
        from .agents import main as agents_main
        agents_main(cmd, rest)
    elif cmd == "daemon":
        from ..app import main as run_daemon
        run_daemon()
    elif cmd == "shell":
        os.execvp("qs", ["qs", "-p", str(ROOT / "shell")])
    elif cmd == "mode":
        if not rest:
            sys.exit("usage: lockdock mode <id>")
        print(call("mode", rest[0]))
    elif cmd in ("cancel", "release", "reload", "reclassify"):
        print(call(cmd))
    elif cmd == "status":
        _status(rest)
    elif cmd == "modes":
        raw = json.loads(MODES_FILE.read_text())
        for m in raw["modes"]:
            print(f"{m['id']:<12} {m.get('icon', '')} {m.get('label', '')}: {m.get('description', '')}")
    elif cmd == "url":
        _url(call("url"))
    elif cmd == "held":
        for n in call("status").get("held", []):
            print(f"[{n['app']}] {n['summary']} — {n['body'][:80]}")
    elif cmd == "log":
        n = int(rest[rest.index("-n") + 1]) if "-n" in rest else 30
        subprocess.run(["tail", f"-n{n}", str(EVENTS_LOG)])
    elif cmd == "config":
        print(MODES_FILE)
    elif cmd == "state-file":
        print(STATE_FILE)
    else:
        sys.exit(f"unknown command {cmd!r}\n\n{USAGE}")
