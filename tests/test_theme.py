import json

import pytest

from lockdock.adapters.json_config import JsonFileWatcher
from lockdock.core.daemon import Daemon
from lockdock.core.theme import ThemeConfig, ThemeService, parse_color, set_dotted
from lockdock.features import theme as theme_feature

from .fakes import (FakeClassifier, FakeClock, FakeConfigSource, FakeJsonDocument, FakePublisher, FakeRunner,
                    FakeSink, make_config)


def make_service(raw=None, **kw):
    changes: list[int] = []
    logs: list[tuple] = []
    doc = FakeJsonDocument(raw, **kw)
    svc = ThemeService(doc, lambda: changes.append(1), lambda kind, **d: logs.append((kind, d)))
    return svc, doc, changes, logs


def test_defaults_match_the_shipped_look():
    t = ThemeConfig.from_dict({})
    assert (t.position, t.margin, t.scale, t.radius, t.icon_size, t.opacity) == ("bottom", 10, 1.0, 22, 36, 1.0)
    assert t.sections == ["pet", "modes", "apps", "agents", "held"]
    assert t.show_unpinned and t.nudge.enabled and not t.autohide.enabled
    assert (t.autohide.reveal_px, t.autohide.hide_delay_ms) == (4, 600)
    assert t.accent_override is None and t.font.family == "" and t.font.size == 14
    assert t.problems == []


def test_example_file_is_the_defaults():
    assert json.loads(theme_feature.EXAMPLE.read_text()) == ThemeConfig().to_dict()


def test_bad_values_fall_back_and_are_reported():
    t = ThemeConfig.from_dict({"position": "left", "margin": "big", "scale": True, "background": "nope",
                               "border": {"width": -1, "color": "#fff"}, "autohide": {"reveal_px": 2.5},
                               "font": 3, "bogus": 1, "nudge": {"enabled": "yes"}})
    assert t.position == "bottom" and t.margin == 10 and t.scale == 1.0
    assert t.background == ThemeConfig().background
    assert t.border.width == 1 and t.autohide.reveal_px == 4 and t.nudge.enabled is True
    keys = {p.split(":")[0] for p in t.problems}
    assert keys == {"position", "margin", "scale", "background", "border.width", "border.color",
                    "autohide.reveal_px", "font", "bogus", "nudge.enabled"}


def test_valid_values_applied():
    t = ThemeConfig.from_dict({"position": "top", "scale": 0.8, "accent_override": "#ff0000",
                               "border": {"width": 2}, "font": {"family": "Inter", "size": 12}})
    assert t.position == "top" and t.scale == 0.8 and t.border.width == 2 and t.font.family == "Inter"
    assert t.border.color == ThemeConfig().border.color  # partial groups keep the other defaults


def test_non_object_file():
    t = ThemeConfig.from_dict([1])
    assert t.position == "bottom" and t.problems


def test_unknown_and_missing_section_ids():
    t = ThemeConfig.from_dict({"sections": ["apps", "hologram", "apps", 3, "modes"]})
    assert t.sections == ["apps", "hologram", "modes"]  # unknown kept for the shell to skip, dupes/non-str dropped
    assert len(t.problems) == 1
    assert ThemeConfig.from_dict({"sections": []}).sections == []
    assert ThemeConfig.from_dict({"sections": "apps"}).sections == ["pet", "modes", "apps", "agents", "held"]


def test_parse_color_forms():
    assert parse_color("#DC1C1C21") == "#DC1C1C21"
    assert parse_color("#1c1c21") == "#FF1C1C21"
    assert parse_color("rgba(1,1,1,0.12)") == "#1FFFFFFF"
    assert parse_color("rgba(0.11,0.11,0.13,0.86)") == "#DB1C1C21"
    assert parse_color("rgba(255, 0, 0, 0.5)") == "#80FF0000"
    assert parse_color("rgb(0,0,0)") == "#FF000000"
    for bad in ("red", "#12", "rgba(1,1,1)", "rgba(1,1,1,2)", "rgba(300,0,0,1)", 5, None):
        assert parse_color(bad) is None


def test_snapshot_shape():
    snap = ThemeConfig().snapshot()
    assert set(snap) == {"position", "margin", "scale", "radius", "background", "border", "accent_override",
                         "font", "icon_size", "sections", "show_unpinned", "autohide", "nudge", "opacity"}
    assert snap["background"] == "#DB1C1C21"
    assert snap["border"] == {"color": "#1FFFFFFF", "width": 1, "off_task_color": "#CCFF594D"}
    json.dumps(snap)
    assert ThemeConfig.from_dict({"accent_override": "rgb(255,0,0)"}).snapshot()["accent_override"] == "#FFFF0000"


def test_set_dotted():
    assert set_dotted({}, "autohide.enabled", True) == {"autohide": {"enabled": True}}
    raw = {"border": {"width": 1}}
    assert set_dotted(raw, "border.color", "#fff") == {"border": {"width": 1, "color": "#fff"}}
    assert raw == {"border": {"width": 1}}  # input untouched
    with pytest.raises(ValueError):
        set_dotted({"margin": 3}, "margin.x", 1)


def test_service_set_writes_and_applies():
    svc, doc, changes, _ = make_service({"scale": 0.9})
    assert svc.set({"key": "autohide.enabled", "value": True})
    assert doc.raw == {"scale": 0.9, "autohide": {"enabled": True}}
    assert svc.theme.autohide.enabled and svc.theme.scale == 0.9
    assert svc.snapshot()["autohide"]["enabled"] is True
    assert changes


def test_service_set_rejects_invalid_without_writing():
    svc, doc, _, _ = make_service({})
    for arg in ({"key": "position", "value": "left"}, {"key": "nope", "value": 1},
                {"key": "border.nope", "value": 1}, {"key": "scale"}, "scale"):
        with pytest.raises(ValueError):
            svc.set(arg)
    assert doc.writes == []


def test_service_set_ignores_preexisting_problems():
    svc, doc, _, _ = make_service({"bogus": 1})
    svc.set({"key": "margin", "value": 4})
    assert doc.raw["margin"] == 4


def test_service_reset_and_get():
    svc, doc, _, _ = make_service({"position": "top"})
    svc.load()
    assert svc.get()["theme"]["position"] == "top"
    svc.reset()
    assert doc.raw == ThemeConfig().to_dict() and svc.theme.position == "bottom"


def test_service_corrupt_file_keeps_previous_theme_and_logs():
    svc, doc, changes, logs = make_service({"position": "top"})
    svc.load()
    doc.error = ValueError("bad json")
    svc.load()
    assert svc.theme.position == "top" and logs[-1][0] == "theme_error"


def test_service_logs_problems_once():
    svc, _, _, logs = make_service({"margin": "x"})
    svc.load()
    svc.load()
    assert [k for k, _ in logs] == ["theme_error"]


def test_json_file_watcher_seeds_writes_and_reads(tmp_path):
    example = tmp_path / "ex.json"
    example.write_text('{"a": 1}')
    w = JsonFileWatcher(tmp_path / "sub" / "t.json", example)
    assert w.read() == {"a": 1}
    w.write({"a": 2})
    assert json.loads((tmp_path / "sub" / "t.json").read_text()) == {"a": 2}
    assert w.read() == {"a": 2}


def test_feature_installs_section_and_commands(tmp_path):
    pub = FakePublisher()
    d = Daemon(config_source=FakeConfigSource(make_config()), classifier=FakeClassifier(), sink=FakeSink(),
               publisher=pub, runner=FakeRunner(), clock=FakeClock())
    for w in theme_feature.install(d, tmp_path / "theme.json"):
        w.close()
    assert d.snapshot()["theme"]["position"] == "bottom"
    assert (tmp_path / "theme.json").exists()  # seeded from the example on first run
    d.handle("theme_set", {"key": "position", "value": "top"})
    assert d.snapshot()["theme"]["position"] == "top"
    assert json.loads((tmp_path / "theme.json").read_text())["position"] == "top"
    assert pub.snapshots[-1]["theme"]["position"] == "top"
    d.handle("theme_reset", None)
    assert d.snapshot()["theme"]["position"] == "bottom"
