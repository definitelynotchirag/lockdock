import json

import pytest

from lockdock.adapters.json_config import JsonFileWatcher
from lockdock.core.daemon import Daemon
from lockdock.core.palette import DARK, LIGHT, ROLES
from lockdock.core.theme import ThemeConfig, ThemeService, parse_color, set_dotted
from lockdock.features import theme as theme_feature

from .fakes import (FakeClassifier, FakeClock, FakeConfigSource, FakeJsonDocument, FakePaletteSource, FakePublisher,
                    FakeRunner, FakeSink, make_config)

MATERIAL_LIGHT = {"primary": "#2c638b", "on_primary": "#ffffff", "primary_container": "#cde5ff",
                  "on_primary_container": "#001d31", "surface": "#f7f9ff", "surface_container": "#ebeef3",
                  "surface_container_high": "#e6e8ee", "surface_container_highest": "#e0e2e8",
                  "on_surface": "#181c20", "on_surface_variant": "#42474e", "outline_variant": "#c2c7ce",
                  "error": "#ba1a1a", "on_error": "#ffffff", "inverse_surface": "#2d3135",
                  "inverse_on_surface": "#eef1f6", "shadow": "#000000"}


def make_service(raw=None, palette=None, **kw):
    changes: list[int] = []
    logs: list[tuple] = []
    doc = FakeJsonDocument(raw, **kw)
    svc = ThemeService(doc, lambda: changes.append(1), lambda kind, **d: logs.append((kind, d)), palette)
    return svc, doc, changes, logs


def test_defaults_are_the_islands_look():
    t = ThemeConfig.from_dict({"palette": "system"})
    assert (t.position, t.margin, t.scale, t.radius, t.icon_size, t.opacity) == ("bottom", 10, 1.0, 20, 34, 1.0)
    assert (t.layout, t.palette, t.gap, t.fill_opacity) == ("islands", "system", 8, 1.0)
    assert t.sections == ["pet", "modes", "apps", "agents", "held"]
    assert t.show_unpinned and t.nudge.enabled and not t.autohide.enabled and t.shadow.enabled
    assert (t.autohide.reveal_px, t.autohide.hide_delay_ms) == (4, 600)
    assert t.accent_override is None and t.font.family == "Inter Display" and t.font.size == 14
    assert t.background is None and t.border.color is None and t.border.off_task_color is None
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


def test_agents_style_and_rows():
    t = ThemeConfig()
    assert (t.agents.style, t.agents.max_rows) == ("pill", 8)
    t = ThemeConfig.from_dict({"agents": {"style": "chips", "max_rows": 5}})
    assert (t.agents.style, t.agents.max_rows) == ("chips", 5) and t.problems == []
    assert t.snapshot()["agents"] == {"style": "chips", "max_rows": 5}
    t = ThemeConfig.from_dict({"agents": {"style": "list", "max_rows": 0, "rows": 3}})
    assert (t.agents.style, t.agents.max_rows) == ("pill", 8)
    assert {p.split(":")[0] for p in t.problems} == {"agents.style", "agents.max_rows", "agents.rows"}
    assert ThemeConfig.from_dict({"agents": {"max_rows": 2.5}}).agents.max_rows == 8
    assert ThemeConfig.from_dict({"agents": "chips"}).problems


def test_prompts_and_mode_strip_keys():
    t = ThemeConfig()
    assert (t.prompts.enabled, t.prompts.max_visible, t.prompts.width) == (True, 3, 360)
    assert t.mode_strip.stay_button is True
    t = ThemeConfig.from_dict({"prompts": {"enabled": False, "max_visible": 5, "width": 420},
                               "mode_strip": {"stay_button": False}})
    assert t.problems == []
    snap = t.snapshot()
    assert snap["prompts"] == {"enabled": False, "max_visible": 5, "width": 420}
    assert snap["mode_strip"] == {"stay_button": False}
    t = ThemeConfig.from_dict({"prompts": {"enabled": "yes", "max_visible": 0, "width": 50, "height": 3},
                               "mode_strip": {"stay_button": 1}})
    assert (t.prompts.enabled, t.prompts.max_visible, t.prompts.width) == (True, 3, 360)
    assert t.mode_strip.stay_button is True
    assert {p.split(":")[0] for p in t.problems} == {"prompts.enabled", "prompts.max_visible", "prompts.width",
                                                     "prompts.height", "mode_strip.stay_button"}
    assert ThemeConfig.from_dict({"prompts": {"max_visible": 2.5}}).prompts.max_visible == 3
    assert ThemeConfig.from_dict({"prompts": True}).problems


def test_service_set_prompts_keys():
    svc, doc, _, _ = make_service({})
    svc.set({"key": "prompts.max_visible", "value": 2})
    svc.set({"key": "mode_strip.stay_button", "value": False})
    assert doc.raw["prompts"] == {"max_visible": 2} and doc.raw["mode_strip"] == {"stay_button": False}
    snap = svc.snapshot()
    assert snap["prompts"]["max_visible"] == 2 and snap["mode_strip"]["stay_button"] is False
    with pytest.raises(ValueError):
        svc.set({"key": "prompts.width", "value": 5000})


def test_service_set_agents_style():
    svc, doc, _, _ = make_service({})
    svc.set({"key": "agents.style", "value": "chips"})
    assert doc.raw["agents"] == {"style": "chips"} and svc.snapshot()["agents"]["style"] == "chips"
    with pytest.raises(ValueError):
        svc.set({"key": "agents.style", "value": "grid"})


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
    assert set(snap) == {"palette", "layout", "position", "margin", "scale", "radius", "gap", "fill_opacity",
                         "background", "border", "shadow", "accent_override", "font", "icon_size", "sections",
                         "show_unpinned", "autohide", "nudge", "agents", "prompts", "mode_strip", "opacity", "colors",
                         "palette_source"}
    assert snap["background"] is None
    assert snap["border"] == {"color": None, "width": 1, "off_task_color": None}
    assert set(snap["colors"]) == set(ROLES) and snap["colors"]["bg"] == DARK.bg
    json.dumps(snap)
    assert ThemeConfig.from_dict({"accent_override": "rgb(255,0,0)"}).snapshot()["accent_override"] == "#FFFF0000"


def test_legacy_colour_keys_still_apply_when_set():
    t = ThemeConfig.from_dict({"palette": "system", "background": "#102030", "border": {"color": "rgba(1,1,1,0.5)"}})
    snap = t.snapshot()
    assert snap["background"] == "#FF102030" and snap["border"]["color"] == "#80FFFFFF"
    assert snap["colors"]["bg"] == DARK.bg  # the role is still published; the shell prefers the legacy key


def test_v1_seeded_file_gets_the_new_look():
    v1 = {"position": "top", "radius": 22, "icon_size": 36, "background": "rgba(0.11,0.11,0.13,0.86)",
          "border": {"color": "rgba(1,1,1,0.12)", "width": 1, "off_task_color": "rgba(1,0.35,0.3,0.8)"},
          "font": {"family": "", "size": 14}, "margin": 30}
    t = ThemeConfig.from_dict(v1)
    assert t.background is None and t.border.color is None and t.radius == 20 and t.icon_size == 34
    assert t.font.family == "Inter Display" and t.position == "top" and t.margin == 30  # real choices kept
    assert t.problems == []
    # a changed v1 value is a choice; a current file (has palette/layout) is taken as written
    assert ThemeConfig.from_dict({"background": "#000000"}).background == "#000000"
    assert ThemeConfig.from_dict({"palette": "dark", "radius": 22}).radius == 22


def test_set_on_a_v1_file_migrates_it():
    svc, doc, _, _ = make_service({"radius": 22, "background": "rgba(0.11,0.11,0.13,0.86)", "margin": 4})
    svc.set({"key": "radius", "value": 22})
    assert doc.raw == {"radius": 22, "margin": 4, "palette": "system"}
    assert svc.theme.radius == 22


def test_layout_and_palette_validation():
    t = ThemeConfig.from_dict({"layout": "grid", "palette": "neon", "shadow": {"opacity": 2}})
    assert t.layout == "islands" and t.palette == "system" and t.shadow.opacity == 0.28
    assert {p.split(":")[0] for p in t.problems} == {"layout", "palette", "shadow.opacity"}
    t = ThemeConfig.from_dict({"layout": "slab", "palette": {"base": "light", "accent": "#ff0000", "bogus": "#fff",
                                                             "danger": "red"}})
    assert t.layout == "slab" and t.palette["accent"] == "#ff0000"
    assert {p.split(":")[0] for p in t.problems} == {"palette.bogus", "palette.danger"}
    snap = t.snapshot()
    assert snap["colors"]["accent"] == "#FFFF0000" and snap["colors"]["bg"] == LIGHT.bg
    assert snap["colors"]["danger"] == LIGHT.danger


def test_service_follows_the_system_palette():
    src = FakePaletteSource(MATERIAL_LIGHT, dark=True)
    svc, _, changes, logs = make_service({"palette": "system"}, palette=src)
    svc.load()
    snap = svc.snapshot()
    assert snap["colors"]["accent"] == "#FF2C638B" and snap["colors"]["bg"] == "#FFEBEEF3"
    assert snap["palette_source"] == "/fake/colors.json (light)"  # light from the file's surface, not the probe
    n = len(changes)
    svc.refresh_palette()
    assert len(changes) == n  # nothing changed: no publish
    src.roles = dict(MATERIAL_LIGHT, primary="#8b2c2c")
    svc.refresh_palette()
    assert len(changes) == n + 1 and svc.snapshot()["colors"]["accent"] == "#FF8B2C2C"
    assert logs[-1][0] == "palette"


def test_service_falls_back_to_builtins_by_scheme():
    src = FakePaletteSource(None, dark=False)
    svc, _, _, _ = make_service({"palette": "system"}, palette=src)
    svc.load()
    assert svc.snapshot()["colors"] == LIGHT.to_dict()
    assert "fallback" in svc.snapshot()["palette_source"]
    src.dark = True
    svc.refresh_palette()
    assert svc.snapshot()["colors"] == DARK.to_dict()
    svc.set({"key": "palette", "value": "light"})
    assert svc.snapshot()["colors"] == LIGHT.to_dict() and svc.snapshot()["palette_source"] == "built-in light"
    got = svc.get()
    assert got["palette"]["source"] == "built-in light" and got["palette"]["colors"]["bg"] == LIGHT.bg


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
    assert doc.raw == {"scale": 0.9, "autohide": {"enabled": True}, "palette": "system"}
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
    for w in theme_feature.install(d, tmp_path / "theme.json", palette=FakePaletteSource(MATERIAL_LIGHT)):
        w.close()
    assert d.snapshot()["theme"]["colors"]["accent"] == "#FF2C638B"
    assert d.snapshot()["theme"]["position"] == "bottom"
    assert (tmp_path / "theme.json").exists()  # seeded from the example on first run
    d.handle("theme_set", {"key": "position", "value": "top"})
    assert d.snapshot()["theme"]["position"] == "top"
    assert json.loads((tmp_path / "theme.json").read_text())["position"] == "top"
    assert pub.snapshots[-1]["theme"]["position"] == "top"
    d.handle("theme_reset", None)
    assert d.snapshot()["theme"]["position"] == "bottom"
