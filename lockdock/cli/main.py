"""lockdock CLI.

  lockdock daemon            run the daemon (foreground)
  lockdock shell             run the Quickshell dock (foreground)
  lockdock mode <id>         switch mode (press again to shorten the exit countdown)
  lockdock cancel            cancel a pending switch
  lockdock status [--json]   current mode, activity verdict, held notifications
  lockdock modes             list modes from modes.json
  lockdock held              list held notifications
  lockdock release           re-deliver held notifications now
  lockdock reload            reload modes.json (also happens automatically)
  lockdock log [-n N]        tail events.jsonl (what was classified and why)
  lockdock config            print the modes.json path
  lockdock theme             print the effective theme (and any problems in theme.json)
  lockdock theme set K V     set a dotted key to a JSON value, e.g. theme set position '"top"'
  lockdock theme reset       restore the default theme
  lockdock theme path        print the theme.json path
  lockdock skill path        print the agent skill directory (skills/lockdock)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ..paths import EVENTS_LOG, MODES_FILE, STATE_FILE, THEME_FILE
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


def _theme(rest: list[str]) -> None:
    sub = rest[0] if rest else "get"
    if sub == "path":
        print(THEME_FILE)
    elif sub == "get":
        res = call("theme_get")
        print(json.dumps(res["theme"], indent=2))
        for p in res["problems"]:
            print(f"problem: {p}", file=sys.stderr)
    elif sub == "set":
        if len(rest) != 3:
            sys.exit("usage: lockdock theme set <dotted.key> <json-value>   (strings need quotes: '\"top\"')")
        try:
            value = json.loads(rest[2])
        except json.JSONDecodeError as e:
            sys.exit(f"value must be JSON ({e}); quote strings, e.g. '\"top\"'")
        print(call("theme_set", {"key": rest[1], "value": value}))
    elif sub == "reset":
        print(call("theme_reset"))
    else:
        sys.exit(f"unknown theme command {sub!r}\n\n{USAGE}")


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return
    cmd, rest = args[0], args[1:]
    if cmd == "daemon":
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
    elif cmd == "held":
        for n in call("status").get("held", []):
            print(f"[{n['app']}] {n['summary']} — {n['body'][:80]}")
    elif cmd == "log":
        n = int(rest[rest.index("-n") + 1]) if "-n" in rest else 30
        subprocess.run(["tail", f"-n{n}", str(EVENTS_LOG)])
    elif cmd == "config":
        print(MODES_FILE)
    elif cmd == "theme":
        _theme(rest)
    elif cmd == "skill":
        if rest[:1] != ["path"]:
            sys.exit("usage: lockdock skill path")
        print(ROOT / "skills" / "lockdock")
    elif cmd == "state-file":
        print(STATE_FILE)
    else:
        sys.exit(f"unknown command {cmd!r}\n\n{USAGE}")
