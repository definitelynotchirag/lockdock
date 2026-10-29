import json

from lockdock.adapters.claude_cli import JsonFileCache
from lockdock.adapters.dbus_notifications import parse_monitor_line
from lockdock.adapters.file_state import AtomicJsonStatePublisher
from lockdock.adapters.json_config import EXAMPLE, JsonConfigLoader


def test_example_config_loads(tmp_path):
    loader = JsonConfigLoader(tmp_path / "modes.json", EXAMPLE)
    cfg = loader.load()
    assert (tmp_path / "modes.json").exists()
    assert cfg.default_mode == "free" and [m.id for m in cfg.modes] == ["free", "writing", "building"]
    assert cfg.get("writing").exit_delay_s == 30 and cfg.get("building").notifications.default == "ask"


def test_state_publisher_atomic(tmp_path):
    p = tmp_path / "state.json"
    AtomicJsonStatePublisher(p).publish({"mode": "free", "label": "✎"})
    assert json.loads(p.read_text())["label"] == "✎" and not (tmp_path / "state.tmp").exists()


def test_cache_roundtrip(tmp_path):
    c = JsonFileCache(tmp_path / "c.json")
    c.put("k", {"verdict": "on", "reason": "r"})
    assert JsonFileCache(tmp_path / "c.json").get("k") == {"verdict": "on", "reason": "r"}


def test_busctl_parse():
    notes, replies = [], []
    call = {"type": "method_call", "member": "Notify", "sender": ":1.9", "cookie": 4,
            "timestamp-realtime": 2_000_000,
            "payload": {"data": ["Slack", 0, "", "Alice", "lunch?", [],
                                 {"urgency": {"type": "y", "data": 1}}, 4000]}}
    parse_monitor_line(json.dumps(call), notes.append, lambda *a: replies.append(a))
    ret = {"type": "method_return", "reply_cookie": 4, "destination": ":1.9", "payload": {"type": "u", "data": [77]}}
    parse_monitor_line(json.dumps(ret), notes.append, lambda *a: replies.append(a))
    ours = dict(call, payload={"data": ["lockdock", 0, "", "s", "b", [], {"x-lockdock": {"data": True}}, -1]})
    parse_monitor_line(json.dumps(ours), notes.append, lambda *a: replies.append(a))
    parse_monitor_line(b"garbage", notes.append, lambda *a: replies.append(a))
    assert len(notes) == 1 and notes[0].summary == "Alice" and notes[0].ts == 2.0
    assert replies == [(4, 77, ":1.9")]


def test_busctl_sink_negative_timeout_is_not_an_option(monkeypatch):
    import subprocess

    from lockdock.adapters import dbus_notifications
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: calls.append(args))
    dbus_notifications.BusctlNotificationSink().send("lockdock", "s", "b")
    args = calls[0]
    assert args[-1] == "-1" and args.index("--") < args.index("call")
