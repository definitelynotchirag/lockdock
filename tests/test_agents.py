import asyncio
import json

import pytest

from lockdock.adapters.json_config import config_from_dict
from lockdock.adapters.proc_scan import ProcScanner, ancestor_pids
from lockdock.cli.agents import install_claude, install_codex, read_payload
from lockdock.core.agent_hooks import CLAUDE_EVENTS, merge_claude_settings, merge_codex_config
from lockdock.core.agents import (DEFAULT_KINDS, AgentRegistry, classify, detect, merge_kinds, parse_hook_event,
                                  window_for)
from lockdock.core.models import AgentState, ProcessInfo, WindowInfo
from lockdock.features.agents import WindowIndex, make_commands, scan_loop

from .fakes import FakeClock, FakeEvents, FakeProcessScanner, FakeSink
from .test_daemon import make_daemon

KITTY, ZSH = ProcessInfo(100, 1, ("kitty",)), ProcessInfo(101, 100, ("/bin/zsh",), "/home/u")
T3 = ProcessInfo(200, 1, ("/tmp/.mount_T3/t3code",))
T3_SERVER = ProcessInfo(201, 200, ("/tmp/.mount_T3/t3code", "--require", "x.cjs", "bin.mjs"))


def claude(pid=102, ppid=101, cwd="/home/u/proj", *args):
    return ProcessInfo(pid, ppid, ("/home/u/.local/bin/claude", *args), cwd)


def t3_claude(pid=202, session="abc"):
    return ProcessInfo(pid, 201, ("/home/u/.local/bin/claude", "--output-format", "stream-json",
                                  "--add-dir", "/home/u/Projects/lockdock", "--add-dir", "/home/u/.t3/att",
                                  f"--session-id={session}"), "/home/u/Projects/lockdock")


def procs(*ps):
    return {p.pid: p for p in ps}


# ---------- kind detection ----------
@pytest.mark.parametrize("cmd,kind", [
    (("/home/u/.local/bin/claude",), "claude"),
    (("claude", "--resume"), "claude"),
    (("node", "/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js"), "claude"),
    (("claude", "-p", "classify this"), None),           # lockdock's own classifier
    (("node", "/usr/lib/node_modules/@openai/codex/bin/codex.js"), "codex"),
    (("/usr/bin/codex",), "codex"),
    (("codex", "exec", "fix it"), None),
    (("codexbar",), None),
    (("/usr/bin/python3", "/home/u/.local/bin/aider", "--model", "x"), "aider"),
    (("opencode",), "opencode"),
    (("node", "/usr/bin/gemini"), "gemini"),
    (("cursor-agent",), "cursor-agent"),
    (("grep", "claude"), None),
    (("vim", "claude.md"), None),
])
def test_classify(cmd, kind):
    p = ProcessInfo(5, 1, cmd)
    k = classify(p, procs(p), DEFAULT_KINDS)
    assert (k.name if k else None) == kind


def test_t3_children_are_t3_and_nested_agents_skipped():
    child = ProcessInfo(203, 202, ("/home/u/.local/bin/claude", "--continue"))   # nested under an agent
    found = detect(procs(T3, T3_SERVER, t3_claude(), child, KITTY, ZSH, claude()), DEFAULT_KINDS)
    assert [(p.pid, k.name) for p, k in found] == [(102, "claude"), (202, "t3")]


def test_custom_kinds_merge():
    kinds = merge_kinds(DEFAULT_KINDS, [{"name": "goose", "glyph": "G", "patterns": ["goose"]},
                                        {"name": "aider", "enabled": False},
                                        {"name": "claude", "glyph": "C"}])
    names = [k.name for k in kinds]
    assert names[0] == "goose" and "aider" not in names
    assert next(k for k in kinds if k.name == "claude").glyph == "C"
    assert next(k for k in kinds if k.name == "claude").patterns == DEFAULT_KINDS[1].patterns
    with pytest.raises(ValueError):
        merge_kinds(DEFAULT_KINDS, [{"glyph": "x"}])
    with pytest.raises(ValueError):
        merge_kinds(DEFAULT_KINDS, [{"name": "x", "patterns": 3}])
    with pytest.raises(ValueError):
        merge_kinds(DEFAULT_KINDS, [{"name": "x", "patterns": ["("]}])


def test_config_agents_section():
    raw = {"modes": [{"id": "free"}], "agents": {"kinds": [{"name": "goose", "patterns": ["goose"]}]}}
    assert config_from_dict(raw).agent_kinds[0].name == "goose"
    assert config_from_dict({"modes": [{"id": "free"}]}).agent_kinds is None


# ---------- window association ----------
def test_ppid_walk_to_window():
    ps = procs(KITTY, ZSH, claude(), T3, T3_SERVER, t3_claude())
    wins = {100: "0xkitty", 200: "0xt3"}
    assert window_for(102, ps, wins.get) == "0xkitty"
    assert window_for(202, ps, wins.get) == "0xt3"
    assert window_for(999, ps, wins.get) is None
    loop = procs(ProcessInfo(1, 2, ("a",)), ProcessInfo(2, 1, ("b",)))   # cycles must terminate
    assert window_for(1, loop, wins.get) is None


def test_window_lookup_cached_per_pid():
    calls = []

    def lookup(pid):
        calls.append(pid)
        return "0xkitty" if pid == 100 else None

    clock = FakeClock()
    r = AgentRegistry(clock, lambda: None, lookup)
    ps = [KITTY, ZSH, claude()]
    r.on_scan(ps)
    n = len(calls)
    clock.t += 3
    r.on_scan(ps)
    assert len(calls) == n and r.agents["claude:102"].window_address == "0xkitty"


def test_window_index_fetches_once_per_scan():
    fetches = []
    idx = WindowIndex(lambda: (fetches.append(1), {7: "0xa"})[1])
    assert idx(7) == "0xa" and idx(8) is None and len(fetches) == 1
    idx.invalidate()
    idx(7)
    assert len(fetches) == 2


# ---------- registry rules ----------
def registry(**kw):
    clock, changes, sink, events = FakeClock(), [], FakeSink(), FakeEvents()
    r = AgentRegistry(clock, lambda: changes.append(1), {100: "0xkitty", 200: "0xt3"}.get, sink=sink,
                      events=events, **kw)
    return r, clock, changes, sink


def ev(state, **payload):
    return parse_hook_event("claude", state, payload)


def test_scan_adds_agent_with_label_and_session():
    r, *_ = registry()
    r.on_scan([KITTY, ZSH, claude(), T3, T3_SERVER, t3_claude()])
    a, t = r.agents["claude:102"], r.agents["t3:202"]
    assert (a.label, a.state, a.window_address) == ("proj", AgentState.IDLE, "0xkitty")
    assert (t.label, t.session_id, t.glyph) == ("lockdock", "abc", "Ⓣ")


def test_hook_matches_by_session_pids_and_cwd():
    r, *_ = registry()
    r.on_scan([KITTY, ZSH, claude(), claude(103, 101, "/home/u/other"), T3, T3_SERVER, t3_claude()])
    assert r.on_event(ev("working", session_id="abc")).id == "t3:202"
    assert r.on_event(parse_hook_event("claude", "working", {"session_id": "s2"}, [999, 103, 101])).id == "claude:103"
    assert r.on_event(ev("working", session_id="s3", cwd="/home/u/proj")).id == "claude:102"
    assert r.agents["claude:102"].session_id == "s3"


def test_hook_only_entry_and_adoption():
    r, clock, changes, _ = registry()
    a = r.on_event(ev("working", session_id="new", cwd="/home/u/proj"))
    assert a.id == "claude:new" and a.pid is None and a.label == "proj"
    clock.t += 1
    r.on_scan([KITTY, ZSH, claude(102, 101, "/home/u/proj", "--resume", "new")])
    assert list(r.agents) == ["claude:102"]
    assert r.agents["claude:102"].state is AgentState.WORKING


def test_needs_input_sticky_until_working_or_focus():
    r, clock, changes, sink = registry()
    r.on_scan([KITTY, ZSH, claude()])
    r.on_event(ev("needs_input", cwd="/home/u/proj", message="Claude needs your permission to use Bash"))
    a = r.agents["claude:102"]
    assert a.state is AgentState.NEEDS_INPUT and a.last_message.startswith("Claude needs")
    assert sink.sent == [{"app": "lockdock", "summary": "claude needs you · proj",
                          "body": "Claude needs your permission to use Bash", "desktop_entry": "",
                          "urgency": 1, "timeout_ms": -1}]
    # scan guesses never override a hook state
    for _ in range(5):
        clock.t += 3
        r.on_scan([KITTY, ZSH, ProcessInfo(102, 101, claude().cmdline, "/home/u/proj", cpu_s=clock.t)])
    assert a.state is AgentState.NEEDS_INPUT
    r.on_focus("0xother")
    assert a.state is AgentState.NEEDS_INPUT
    r.on_focus("0xkitty")
    assert a.state is AgentState.WORKING
    r.on_event(ev("needs_input", cwd="/home/u/proj"))
    r.on_event(ev("done", cwd="/home/u/proj"))
    assert a.state is AgentState.DONE and len(sink.sent) == 2


def test_repeated_working_events_are_debounced():
    r, clock, changes, _ = registry()
    r.on_scan([KITTY, ZSH, claude()])
    r.on_event(ev("working", cwd="/home/u/proj", tool_name="Bash"))
    n = len(changes)
    for _ in range(20):
        r.on_event(ev("working", cwd="/home/u/proj", tool_name="Read"))
    assert len(changes) == n


def test_cpu_guess_for_unhooked_agents():
    r, clock, *_ = registry()
    base = claude()
    r.on_scan([KITTY, ZSH, base])
    for cpu in (1.0, 2.0):
        clock.t += 3
        r.on_scan([KITTY, ZSH, ProcessInfo(102, 101, base.cmdline, base.cwd, cpu_s=cpu)])
    assert r.agents["claude:102"].state is AgentState.WORKING
    for _ in range(4):
        clock.t += 3
        r.on_scan([KITTY, ZSH, ProcessInfo(102, 101, base.cmdline, base.cwd, cpu_s=2.0)])
    assert r.agents["claude:102"].state is AgentState.IDLE


def test_unseen_dropped_after_10s_but_done_kept_10min():
    r, clock, *_ = registry()
    r.on_scan([KITTY, ZSH, claude(), claude(103, 101, "/home/u/b")])
    r.on_event(parse_hook_event("claude", "done", {}, [103]))
    clock.t += 5
    r.on_scan([KITTY, ZSH])
    assert set(r.agents) == {"claude:102", "claude:103"}
    clock.t += 6
    r.on_scan([KITTY, ZSH])
    assert set(r.agents) == {"claude:103"}
    clock.t += 600
    r.on_scan([KITTY, ZSH])
    assert r.agents == {}


def test_hook_only_done_retention_and_ttl():
    r, clock, *_ = registry()
    r.on_event(ev("done", session_id="a", cwd="/x"))
    r.on_event(ev("working", session_id="b", cwd="/y"))
    clock.t += 601
    r.on_scan([])
    assert set(r.agents) == {"claude:b"}
    clock.t += 1800
    r.on_scan([])
    assert r.agents == {}


def test_snapshot_ordering():
    r, clock, *_ = registry()
    r.on_scan([KITTY, ZSH, claude(102, 101, "/p/a"), claude(103, 101, "/p/b"), claude(104, 101, "/p/c"),
               claude(105, 101, "/p/d")])
    r.on_event(parse_hook_event("claude", "done", {}, [102]))
    r.on_event(parse_hook_event("claude", "working", {}, [103]))
    r.on_event(parse_hook_event("claude", "needs_input", {}, [105]))
    assert [(a["label"], a["state"]) for a in r.snapshot()] == [
        ("d", "needs_input"), ("b", "working"), ("c", "idle"), ("a", "done")]
    json.dumps(r.snapshot())


# ---------- hook JSON ----------
def test_parse_claude_hook_json():
    e = parse_hook_event("claude", "needs_input", {
        "session_id": "s1", "cwd": "/home/u/proj/", "hook_event_name": "Notification",
        "message": "Claude needs\n your permission", "transcript_path": "/x"}, ["12", 13])
    assert (e.session_id, e.cwd, e.hook_event, e.message, e.pids) == (
        "s1", "/home/u/proj", "Notification", "Claude needs your permission", (12, 13))
    assert parse_hook_event("claude", "working", {"tool_name": "Bash"}).message == "running Bash"
    with pytest.raises(ValueError):
        parse_hook_event("claude", "bogus", {})


def test_parse_codex_notify_json():
    payload = read_payload(['{"type": "agent-turn-complete", "thread-id": "t1", "cwd": "/w", '
                            '"last-assistant-message": "Done, want me to push?"}'])
    e = parse_hook_event("codex", "needs_input", payload)
    assert (e.session_id, e.cwd, e.message, e.hook_event) == ("t1", "/w", "Done, want me to push?",
                                                             "agent-turn-complete")


# ---------- install-hooks merge ----------
EXISTING = {"model": "opus", "hooks": {
    "Notification": [{"matcher": "*", "hooks": [{"type": "command", "command": "other-tool notify"}]}],
    "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "atuin hook"}]}]}}


def test_merge_claude_settings_preserves_and_is_idempotent():
    new, added = merge_claude_settings(EXISTING)
    assert added == list(CLAUDE_EVENTS)
    assert new["model"] == "opus" and EXISTING["hooks"]["Notification"][0]["hooks"][0]["command"] == "other-tool notify"
    assert new["hooks"]["Notification"][0] == EXISTING["hooks"]["Notification"][0]
    assert new["hooks"]["Notification"][1]["hooks"][0]["command"] == "lockdock agent-event claude needs_input"
    assert new["hooks"]["PreToolUse"][1]["matcher"] == "*"
    assert "matcher" not in new["hooks"]["Stop"][0]
    again, added2 = merge_claude_settings(new)
    assert again == new and added2 == []
    with pytest.raises(ValueError):
        merge_claude_settings({"hooks": []})


def test_install_claude_on_temp_file(tmp_path, capsys):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(EXISTING))
    assert install_claude(path, dry=True) == list(CLAUDE_EVENTS)
    assert json.loads(path.read_text()) == EXISTING and "+" in capsys.readouterr().out   # dry-run: diff only
    install_claude(path, dry=False)
    backup = tmp_path / "settings.json.bak-lockdock"
    assert json.loads(backup.read_text()) == EXISTING
    first = path.read_text()
    assert install_claude(path, dry=False) == []
    assert path.read_text() == first and json.loads(backup.read_text()) == EXISTING
    fresh = tmp_path / "none" / "settings.json"
    install_claude(fresh, dry=False)
    assert set(json.loads(fresh.read_text())["hooks"]) == set(CLAUDE_EVENTS)


def test_merge_codex_config(tmp_path):
    text = 'model = "gpt"\n\n[features]\nhooks = true\n'
    new, status = merge_codex_config(text)
    assert status == "added"
    assert new.index("notify = [") < new.index("[features]") and new.endswith("hooks = true\n")
    assert merge_codex_config(new) == (new, "present")
    assert merge_codex_config('notify = ["say"]\n')[1] == "other"
    assert merge_codex_config('[x]\nnotify = 1\n')[1] == "added"        # a table's notify is not the top-level one
    path = tmp_path / "config.toml"
    path.write_text(text)
    assert install_codex(path, dry=False) == "added" and install_codex(path, dry=False) == "present"
    assert (tmp_path / "config.toml.bak-lockdock").read_text() == text


# ---------- adapters and wiring ----------
def test_proc_scanner_reads_fake_proc(tmp_path):
    import os
    for pid, ppid, argv in ((10, 1, [b"/bin/zsh"]), (11, 10, [b"claude", b"--resume", b"x"]), (12, 10, [])):
        d = tmp_path / str(pid)
        d.mkdir()
        (d / "stat").write_text(f"{pid} (a b) S {ppid} 0 0 0 0 0 0 0 0 0 250 50 0 0 20 0 1 0")
        (d / "cmdline").write_bytes(b"\0".join(argv) + (b"\0" if argv else b""))
        os.symlink("/tmp", d / "cwd")
    ps = {p.pid: p for p in ProcScanner(tmp_path, uid=os.getuid()).scan()}
    assert set(ps) == {10, 11}
    assert ps[11].cmdline == ("claude", "--resume", "x") and ps[11].ppid == 10 and ps[11].cwd == "/tmp"
    assert ps[11].cpu_s == 300 / os.sysconf("SC_CLK_TCK")
    assert ancestor_pids(11, tmp_path) == [11, 10]


def test_feature_commands_and_focus(tmp_path):
    d, pub, sink, spawner = make_daemon(tmp_path)
    from lockdock.features import agents as feature
    r = AgentRegistry(d.clock, d.publish, {100: "0xkitty"}.get, sink=d.sink)
    focused = []
    cmds = make_commands(r, focused.append)
    r.on_scan([KITTY, ZSH, claude()])
    assert cmds["agent_event"]({"kind": "claude", "state": "needs_input", "pids": [999, 102],
                                "payload": {"message": "hi"}}) == "claude:102"
    assert cmds["agent_event"]({"kind": "claude", "state": "nope"}).startswith("bad agent event")
    assert cmds["agent_focus"]("claude:102") == "focused claude:102" and focused == ["0xkitty"]
    assert cmds["agent_focus"]("nope") == "no agent 'nope'"
    assert cmds["agents"](None)[0]["state"] == "needs_input"
    assert sink.sent[-1]["summary"] == "claude needs you · proj"
    # the real install() wires a section, the commands and the focus listener
    coros = feature.install(d)
    assert d.snapshot()["agents"] == [] and d.handle("agent_focus", "x") == "no agent 'x'"
    d.on_focus(WindowInfo("kitty", "zsh", address="0xkitty"))
    for c in coros:
        c.close()
    spawner.discard()


def test_scan_loop_runs_registry():
    clock = FakeClock()
    r = AgentRegistry(clock, lambda: None)
    idx = WindowIndex(dict)

    async def run():
        task = asyncio.ensure_future(scan_loop(FakeProcessScanner([KITTY, ZSH, claude()]), r, idx, clock, 0))
        for _ in range(20):
            await asyncio.sleep(0)
        task.cancel()

    asyncio.run(run())
    assert "claude:102" in r.agents


def test_own_notifications_skip_the_gate():
    """Agent notifications go through BusctlNotificationSink, which tags them x-lockdock;
    the observer drops those, so a mode that holds everything never holds an agent prompt."""
    from lockdock.adapters.dbus_notifications import parse_monitor_line
    notes = []
    call = {"type": "method_call", "member": "Notify", "payload": {
        "data": ["lockdock", 0, "", "claude needs you · proj", "b", [], {"x-lockdock": {"data": True}}, -1]}}
    parse_monitor_line(json.dumps(call), notes.append, lambda *a: None)
    assert notes == []
