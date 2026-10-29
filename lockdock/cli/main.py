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
  lockdock prompts [--json]  open decision cards (site / notification / verdict)
  lockdock prompt <id> <action>
                             press a card button: later | dismiss | stay | switch
  lockdock reload            reload modes.json (also happens automatically)
  lockdock log [-n N]        tail events.jsonl (what was classified and why)
  lockdock classify <class> "<title>" [--mode <id>] [--url <url>] [--cached]
                             run the configured classifier once (live unless --cached) and show
                             verdict, reason, source and ms; for tuning mode descriptions
  lockdock config            print the modes.json path
  lockdock agents [--json]   running coding agents and whether they need you
  lockdock agent focus <id>  focus an agent's window
  lockdock agents install-hooks [--claude] [--codex] [--dry-run]
                             report agent state from Claude Code / Codex hooks
  lockdock agent-event <kind> <state> [json]
                             (used by hooks) report an agent's state; JSON on stdin
  lockdock pet               the pet's mood, size and line
  lockdock pet calm          reset the pet (also: click it)
  lockdock pet mood <m>      preview content|suspicious|annoyed|furious, or `auto`
  lockdock pet mute|unmute   keep the mood, drop the lines and the growth
  lockdock pet pack <name>   switch sprite pack (lockdock pet packs lists them)
  lockdock pet say "<text>"  show a line now
  lockdock theme             print the effective theme, the resolved palette and its source (and problems)
  lockdock theme set K V     set a dotted key to a JSON value, e.g. theme set position '"top"'
  lockdock theme reset       restore the default theme
  lockdock theme path        print the theme.json path
  lockdock pin [on|off|toggle]
                             pin the dock: reserve its space so windows stop at it
  lockdock unpin             let windows cover the dock again (theme `pinned`)
  lockdock skill path        print the agent skill directory (skills/lockdock)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ..paths import EVENTS_LOG, MODES_FILE, PET_FILE, STATE_FILE, THEME_FILE
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


def _prompts(rest: list[str]) -> None:
    res = call("prompts")
    if "--json" in rest:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return
    if not res:
        print("no open prompts")
    for p in res:
        print(f"{p['id']:<5} {p['kind']:<12} {p['title']} · {p['subtitle']}")
        if p.get("body"):
            print(f"      {p['body']}")
        if p.get("tag"):
            print(f"      [{p['tag']['label']}] {p['tag']['detail']} ({p['tag']['level']})")
        if p.get("actions"):
            print("      actions: " + "  ".join(f"{a['id']}={a['label']!r}" for a in p["actions"]))
        if p.get("expires_ms"):
            print(f"      expires_ms: {p['expires_ms']}")


def _classify(rest: list[str]) -> None:
    opts: dict = {}
    words: list[str] = []
    it = iter(rest)
    for a in it:
        if a in ("--mode", "--url"):
            opts[a[2:]] = next(it, "")
        elif a == "--cached":
            opts["cached"] = True
        else:
            words.append(a)
    if len(words) != 2:
        sys.exit('usage: lockdock classify <class> "<title>" [--mode <id>] [--url <url>] [--cached]')
    res = call("classify", {"cls": words[0], "title": words[1], **opts})
    if not isinstance(res, dict):
        sys.exit(str(res))
    print(f"{res['mode']}: {res['verdict']}  ({res['reason']})")
    print(f"  source: {res['source']} via {res['provider']}  {res['ms']} ms")
    r = res.get("rules")
    print(f"  rules:  {r['verdict']} ({r['reason']}); the daemon decides by rule, not the classifier"
          if r else "  rules:  no rule matches; the daemon asks the classifier")


def _pet(rest: list[str]) -> None:
    res = call("pet", rest)
    if rest and rest[0] == "packs" and isinstance(res, list):
        for p in res:
            print(f"{p['name']:<14} {p['source']:<9} {p['title']} by {p['author']}  {p['dir']}")
    elif isinstance(res, dict):
        flags = " ".join(f for f, on in (("forced", res.get("forced")), ("muted", res.get("muted"))) if on)
        print(f"{res['name']} ({res['pack']}): {res['mood']}  scale {res['scale']}  "
              f"off task {res['off_seconds']}s  {flags}".rstrip())
        if res.get("line"):
            print(f"  \"{res['line']}\"")
        print(f"config: {PET_FILE}")
    else:
        print(res)


def _theme(rest: list[str]) -> None:
    sub = rest[0] if rest else "get"
    if sub == "path":
        print(THEME_FILE)
    elif sub == "get":
        res = call("theme_get")
        print(json.dumps(res["theme"], indent=2))
        pal = res.get("palette") or {}
        if pal:
            print(f"\npalette: {pal['source']}")
            for role, colour in pal["colors"].items():
                print(f"  {role:<20} {colour}")
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
    elif cmd == "prompts":
        _prompts(rest)
    elif cmd == "prompt":
        if len(rest) != 2:
            sys.exit("usage: lockdock prompt <id> later|dismiss|stay|switch")
        print(call("prompt_act", {"id": rest[0], "action": rest[1]}))
    elif cmd == "log":
        n = int(rest[rest.index("-n") + 1]) if "-n" in rest else 30
        subprocess.run(["tail", f"-n{n}", str(EVENTS_LOG)])
    elif cmd == "classify":
        _classify(rest)
    elif cmd == "pet":
        _pet(rest)
    elif cmd == "config":
        print(MODES_FILE)
    elif cmd == "theme":
        _theme(rest)
    elif cmd in ("pin", "unpin"):
        arg = "off" if cmd == "unpin" else (rest[0] if rest else "on")
        if (cmd == "unpin" and rest) or arg not in ("on", "off", "toggle"):
            sys.exit("usage: lockdock pin [on|off|toggle] | lockdock unpin")
        print(call("pin", arg))
    elif cmd == "skill":
        if rest[:1] != ["path"]:
            sys.exit("usage: lockdock skill path")
        print(ROOT / "skills" / "lockdock")
    elif cmd == "state-file":
        print(STATE_FILE)
    else:
        sys.exit(f"unknown command {cmd!r}\n\n{USAGE}")
