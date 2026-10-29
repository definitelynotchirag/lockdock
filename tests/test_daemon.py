import json

import pytest

from lockdock.adapters.control_socket import handle_line
from lockdock.core.daemon import Daemon
from lockdock.core.models import Notification, WindowInfo
from lockdock.core.state import StateSnapshot

from .fakes import (FakeClassifier, FakeClock, FakeConfigSource, FakePublisher, FakeRunner, FakeSink, Spawner,
                    make_config)

KEYS = {"mode", "modes", "pending", "activity", "held", "held_count", "agents", "pet", "theme", "updated_ms"}


def make_daemon(tmp_path, cfg=None, error=None):
    pub, sink, spawner = FakePublisher(), FakeSink(), Spawner()
    src = FakeConfigSource(cfg or make_config())
    d = Daemon(config_source=src, classifier=FakeClassifier(), sink=sink, publisher=pub, runner=FakeRunner(),
               clock=FakeClock(), events_path=tmp_path / "events.jsonl", spawn=spawner)
    src.error = error
    return d, pub, sink, spawner


def test_snapshot_shape(tmp_path):
    d, pub, _, spawner = make_daemon(tmp_path)
    d.start(WindowInfo("kitty", "zsh"))
    st = pub.snapshots[-1]
    assert set(st) == KEYS
    assert st["mode"] == "free" and st["pending"] is None
    assert st["agents"] == [] and st["pet"] == {} and st["theme"] == {}
    assert st["modes"][1] == {"id": "writing", "label": "Writing", "icon": "●", "color": "auto",
                              "apps": ["md.obsidian.Obsidian", "helium"], "description": ""}
    assert st["updated_ms"] == 1000000
    json.dumps(st)
    spawner.drain()
    assert pub.snapshots[-1]["activity"]["verdict"] == "on"


def test_register_section(tmp_path):
    d, *_ = make_daemon(tmp_path)
    d.register_section("agents", lambda: [{"name": "claude", "needs_input": True}])
    d.register_section("weather", lambda: {"temp": 3})
    st = d.snapshot()
    assert st["agents"][0]["name"] == "claude" and st["weather"] == {"temp": 3}
    with pytest.raises(ValueError):
        d.register_section("mode", dict)
    with pytest.raises(ValueError):
        StateSnapshot().register_section("held_count", dict)


def test_pending_and_held_in_snapshot(tmp_path):
    d, pub, _, spawner = make_daemon(tmp_path)
    d.handle("mode", "writing")
    d.handle("mode", "building")
    st = pub.snapshots[-1]
    assert st["pending"] == {"mode": "building", "deadline_ms": 1030000, "total_ms": 30000}
    d.gate.on_notify(Notification(app="Slack", summary="lunch?", body=""))
    assert pub.snapshots[-1]["held_count"] == 1
    assert pub.snapshots[-1]["held"][0]["summary"] == "lunch?"
    spawner.discard()


def test_switch_releases_held(tmp_path):
    d, pub, sink, spawner = make_daemon(tmp_path)
    d.handle("mode", "writing")
    d.gate.on_notify(Notification(app="Slack", summary="lunch?", body="b"))
    d.modes.activate("free")
    assert sink.sent[0]["body"] == "b\n(while you were in Writing)"
    assert pub.snapshots[-1]["held_count"] == 0
    spawner.discard()


def test_command_dispatch(tmp_path):
    d, pub, sink, spawner = make_daemon(tmp_path)
    assert d.handle("mode", "writing") == "switched to writing"
    assert d.handle("cancel", None) == "cancelled"
    assert d.handle("release", None) == "released 0"
    assert d.handle("reload", None) == "reloaded"
    assert d.handle("reclassify", None) == "scheduled"
    assert d.handle("status", None)["mode"] == "writing"
    assert d.handle("bogus", None) == "unknown command 'bogus'"
    assert d.handle(None, None) == "unknown command None"
    d.register_command("ping", lambda arg: f"pong {arg}")
    assert d.handle("ping", 1) == "pong 1"
    kinds = [json.loads(line)["kind"] for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert kinds == ["switch", "cancel", "reload"]
    spawner.discard()


def test_socket_line_protocol(tmp_path):
    d, *_, spawner = make_daemon(tmp_path)
    assert handle_line(d, b'{"cmd": "mode", "arg": "writing"}\n') == {"ok": True, "result": "switched to writing"}
    assert handle_line(d, b"") == {"ok": True, "result": "unknown command None"}
    assert handle_line(d, b"not json")["ok"] is False
    spawner.discard()


def test_reload_error_keeps_config(tmp_path):
    d, *_ = make_daemon(tmp_path, error=ValueError("bad json"))
    assert d.handle("reload", None) == "modes.json error: bad json"
    rec = json.loads((tmp_path / "events.jsonl").read_text().splitlines()[-1])
    assert rec["kind"] == "config_error" and rec["mode"] == "free"


def test_config_listeners_and_mode_fallback(tmp_path):
    d, _, _, spawner = make_daemon(tmp_path)
    d.handle("mode", "writing")
    seen = []
    d.config_listeners.append(lambda cfg: seen.append(cfg.llm_model))
    cfg = make_config(llm_model="sonnet")
    cfg.modes = [m for m in cfg.modes if m.id != "writing"]
    d.apply_config(cfg)
    assert seen == ["sonnet"] and d.modes.mode == "free"
    spawner.discard()
