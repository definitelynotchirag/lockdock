import asyncio
import json

import pytest

from lockdock.adapters.json_config import config_from_dict
from lockdock.adapters.system_palette import GsettingsSchemeProbe, MatugenPaletteSource
from lockdock.core.palette import DARK, LIGHT, ROLES, Palette, luminance, mix, palette_problems, resolve

from .test_theme import MATERIAL_LIGHT

MATERIAL_DARK = {"primary": "#99ccfa", "on_primary": "#003350", "primary_container": "#084b72",
                 "on_primary_container": "#cde5ff", "surface": "#101418", "surface_container": "#1c2024",
                 "surface_container_high": "#262a2f", "surface_container_highest": "#31353a",
                 "on_surface": "#e0e2e8", "on_surface_variant": "#c2c7ce", "outline_variant": "#42474e",
                 "error": "#ffb4ab", "on_error": "#690005", "secondary": "#b8c8da", "tertiary": "#d2bfe7",
                 "inverse_surface": "#e0e2e8", "inverse_on_surface": "#2d3135", "shadow": "#000000"}


def test_builtins_are_complete_and_opposite():
    assert set(DARK.to_dict()) == set(LIGHT.to_dict()) == set(ROLES)
    assert DARK.dark and not LIGHT.dark
    for p in (DARK, LIGHT):  # text is readable on the island fill, and on the active pill
        assert abs(luminance(p.text) - luminance(p.bg)) > 0.5
        assert abs(luminance(p.on_accent_container) - luminance(p.accent_container)) > 0.4
        assert abs(luminance(p.bubble_text) - luminance(p.bubble)) > 0.5


def test_material_mapping():
    p = Palette.from_material(MATERIAL_LIGHT, dark=False)
    assert p.bg == "#FFEBEEF3" and p.bg_elevated == "#FFE6E8EE" and p.surface == "#FFE0E2E8"
    assert p.text == "#FF181C20" and p.text_muted == "#FF42474E" and p.outline == "#FFC2C7CE"
    assert (p.accent, p.on_accent) == ("#FF2C638B", "#FFFFFFFF")
    assert (p.accent_container, p.on_accent_container) == ("#FFCDE5FF", "#FF001D31")
    assert (p.danger, p.on_danger) == ("#FFBA1A1A", "#FFFFFFFF")
    assert (p.bubble, p.bubble_text) == ("#FF2D3135", "#FFEEF1F6")
    assert p.surface_hover == mix(p.surface, p.text, 0.10)
    # roles the file lacks come from the built-in of the same darkness
    assert p.secondary == LIGHT.secondary and p.success == LIGHT.success
    assert Palette.from_material({}, dark=True) == DARK
    assert Palette.from_material({"primary": "nope"}, dark=False).accent == LIGHT.accent


def test_resolve_system_detects_darkness_from_the_file():
    pal, src = resolve("system", MATERIAL_DARK, "/x/colors.json", prefers_dark=False)
    assert pal.dark and pal.accent == "#FF99CCFA" and src == "/x/colors.json (dark)"
    assert pal.success == DARK.success
    pal, src = resolve("system", MATERIAL_LIGHT, "/x/colors.json", prefers_dark=True)
    assert not pal.dark and src.endswith("(light)")


def test_resolve_fallbacks_and_forced():
    assert resolve("system", None, "", prefers_dark=True)[0] == DARK
    assert resolve("system", None, "", prefers_dark=False)[0] == LIGHT
    assert "fallback" in resolve("system", None, "", True)[1]
    assert resolve("dark", MATERIAL_LIGHT, "/x", False) == (DARK, "built-in dark")
    assert resolve("light", MATERIAL_DARK, "/x", True) == (LIGHT, "built-in light")


def test_resolve_overrides_merge_over_the_base():
    pal, src = resolve({"accent": "#ff0000", "bubble": "rgba(1,1,1,0.5)"}, MATERIAL_LIGHT, "/x", True)
    assert pal.accent == "#FFFF0000" and pal.bubble == "#80FFFFFF" and pal.bg == "#FFEBEEF3"
    assert src == "/x (light) + 2 overrides"
    pal, _ = resolve({"base": "dark", "text": "#ffffff", "junk": "#000", "danger": "red"}, MATERIAL_LIGHT, "/x", False)
    assert pal.text == "#FFFFFFFF" and pal.bg == DARK.bg and pal.danger == DARK.danger


def test_palette_problems():
    assert palette_problems("system") == palette_problems("dark") == palette_problems({"accent": "#ffffff"}) == []
    assert palette_problems("neon") and palette_problems(3)
    assert len(palette_problems({"base": "x", "nope": "#fff", "accent": 1})) == 3


def test_mode_colour_auto():
    raw = {"modes": [{"id": "a"}, {"id": "b", "color": "auto"}, {"id": "c", "color": "#3b82f6"}]}
    cfg = config_from_dict(raw)
    assert [m.color for m in cfg.modes] == ["auto", "auto", "#3b82f6"]
    from lockdock.adapters.json_config import EXAMPLE
    assert {m["color"] for m in json.loads(EXAMPLE.read_text())["modes"]} == {"auto"}


def test_matugen_source_picks_first_existing_and_watches(tmp_path):
    class Probe:
        dark = False
        calls = 0

        def prefers_dark(self):
            Probe.calls += 1
            return self.dark

    probe = Probe()
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    src = MatugenPaletteSource([a, b], probe, poll_s=0.01, scheme_every=1)
    assert src.material() is None and src.prefers_dark() is False
    b.write_text(json.dumps(MATERIAL_LIGHT))
    assert src.material() == (MATERIAL_LIGHT, str(b))
    a.write_text("not json")
    assert src.material() is None  # the first existing file wins, even when broken

    seen: list[int] = []

    async def run():
        task = asyncio.create_task(src.watch(lambda: seen.append(1)))
        await asyncio.sleep(0.05)
        assert seen == []
        a.write_text(json.dumps(MATERIAL_DARK))
        await asyncio.sleep(0.05)
        assert seen
        n = len(seen)
        probe.dark = True
        await asyncio.sleep(0.05)
        assert len(seen) > n and src.prefers_dark() is True
        task.cancel()

    asyncio.run(run())


def test_gsettings_probe_without_gsettings(monkeypatch):
    import subprocess

    def boom(*a, **k):
        raise FileNotFoundError("gsettings")

    monkeypatch.setattr(subprocess, "run", boom)
    assert GsettingsSchemeProbe().prefers_dark() is True

    class R:
        def __init__(self, out):
            self.stdout = out

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: R("'prefer-light'\n"))
    assert GsettingsSchemeProbe().prefers_dark() is False
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: R("'prefer-dark'\n"))
    assert GsettingsSchemeProbe().prefers_dark() is True


@pytest.mark.parametrize("bad", ["red", None, 3])
def test_palette_rejects_bad_colours(bad):
    with pytest.raises(ValueError):
        DARK.merged({"accent": bad})
