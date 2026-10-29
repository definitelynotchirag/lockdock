"""Theme: every visual knob of the dock, validated, with defaults that match the shipped look.

Colours come from a palette (`core/palette.py`): the desktop's Material You scheme by default.
The legacy colour keys (`background`, `border.color`, `border.off_task_color`) are null unless
set, and override the palette when set."""
from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from typing import Any

from .palette import Palette, palette_problems, parse_color, resolve
from .ports import JsonDocument, PaletteSource

POSITIONS = ("bottom", "top")
LAYOUTS = ("islands", "slab")
DEFAULT_SECTIONS = ("pet", "modes", "apps", "agents", "held")

# Values the pre-palette theme.example.json wrote into every theme.json. A file without a
# `palette` or `layout` key is from then: these values were seeded, not chosen, so they are
# dropped (see `upgrade_v1`) and the new defaults apply.
V1_SEEDED: dict[str, Any] = {
    "background": "rgba(0.11,0.11,0.13,0.86)", "radius": 22, "icon_size": 36,
    "border.color": "rgba(1,1,1,0.12)", "border.off_task_color": "rgba(1,0.35,0.3,0.8)",
    "font.family": "",
}


def upgrade_v1(raw: Any) -> Any:
    """A pre-palette theme.json without its seeded defaults, marked as current (`palette` set)."""
    if not isinstance(raw, dict) or "palette" in raw or "layout" in raw:
        return raw
    out = copy.deepcopy(raw)
    for key, seeded in V1_SEEDED.items():
        group, _, leaf = key.rpartition(".")
        node = out.get(group) if group else out
        if isinstance(node, dict) and leaf in node and node[leaf] == seeded:
            del node[leaf]
    out["palette"] = "system"
    return out


def _num(lo: float, hi: float) -> Callable[[Any], bool]:
    return lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi


def _int(lo: int, hi: int) -> Callable[[Any], bool]:
    return lambda v: _num(lo, hi)(v) and float(v).is_integer()


def _is_bool(v: Any) -> bool:
    return isinstance(v, bool)


def _is_str(v: Any) -> bool:
    return isinstance(v, str)


def _is_color(v: Any) -> bool:
    return parse_color(v) is not None


def _color_or_null(v: Any) -> bool:
    return v is None or _is_color(v)


@dataclass
class BorderTheme:
    """Island / card border: colour (null = palette outline), width in px, colour while off task
    (null = palette danger)."""
    color: str | None = None
    width: float = 1
    off_task_color: str | None = None


@dataclass
class FontTheme:
    """Font family ("" = system default; a missing family falls back to it) and base size in px."""
    family: str = "Inter Display"
    size: float = 14


@dataclass
class AutohideTheme:
    """Slide the dock off-screen when idle; reveal_px is the hover strip at the screen edge."""
    enabled: bool = False
    reveal_px: int = 4
    hide_delay_ms: int = 600


@dataclass
class NudgeTheme:
    """The red 'off task' bubble."""
    enabled: bool = True


@dataclass
class ShadowTheme:
    """Soft drop shadow under each island (and the slab card)."""
    enabled: bool = True
    opacity: float = 0.28


_VALIDATORS: dict[str, tuple[Callable[[Any], bool], str]] = {
    "position": (lambda v: v in POSITIONS, '"bottom" or "top"'),
    "margin": (_num(0, 1000), "a number 0..1000"),
    "scale": (_num(0.3, 4), "a number 0.3..4"),
    "radius": (_num(0, 200), "a number 0..200"),
    "layout": (lambda v: v in LAYOUTS, '"islands" or "slab"'),
    "gap": (_num(0, 200), "a number 0..200"),
    "fill_opacity": (_num(0, 1), "a number 0..1"),
    "background": (_color_or_null, "null, #AARRGGBB, #RRGGBB or rgba(r,g,b,a)"),
    "accent_override": (lambda v: v is None or _is_color(v), "null or a colour"),
    "icon_size": (_num(8, 256), "a number 8..256"),
    "show_unpinned": (_is_bool, "true or false"),
    "opacity": (_num(0, 1), "a number 0..1"),
    "border.color": (_color_or_null, "null or a colour"),
    "border.width": (_num(0, 50), "a number 0..50"),
    "border.off_task_color": (_color_or_null, "null or a colour"),
    "font.family": (_is_str, "a string"),
    "font.size": (_num(4, 100), "a number 4..100"),
    "autohide.enabled": (_is_bool, "true or false"),
    "autohide.reveal_px": (_int(1, 100), "an integer 1..100"),
    "autohide.hide_delay_ms": (_int(0, 600000), "an integer 0..600000"),
    "nudge.enabled": (_is_bool, "true or false"),
    "shadow.enabled": (_is_bool, "true or false"),
    "shadow.opacity": (_num(0, 1), "a number 0..1"),
}
_GROUPS = ("border", "font", "autohide", "nudge", "shadow")


@dataclass
class ThemeConfig:
    """The dock's look. `from_dict` never raises: bad values fall back to the default and are
    listed in `problems`. `snapshot()` is what the shell reads as `st.theme`."""
    palette: Any = "system"
    layout: str = "islands"
    position: str = "bottom"
    margin: float = 10
    scale: float = 1.0
    radius: float = 20
    gap: float = 8
    fill_opacity: float = 1.0
    background: str | None = None
    border: BorderTheme = field(default_factory=BorderTheme)
    shadow: ShadowTheme = field(default_factory=ShadowTheme)
    accent_override: str | None = None
    font: FontTheme = field(default_factory=FontTheme)
    icon_size: float = 34
    sections: list[str] = field(default_factory=lambda: list(DEFAULT_SECTIONS))
    show_unpinned: bool = True
    autohide: AutohideTheme = field(default_factory=AutohideTheme)
    nudge: NudgeTheme = field(default_factory=NudgeTheme)
    opacity: float = 1.0
    problems: list[str] = field(default_factory=list, compare=False)

    @classmethod
    def from_dict(cls, raw: Any) -> ThemeConfig:
        """Build from parsed theme.json; invalid or unknown entries are reported in `.problems`."""
        theme = cls()
        raw = upgrade_v1(raw)
        if not isinstance(raw, dict):
            theme.problems.append(f"theme.json must be an object, got {type(raw).__name__}")
            return theme
        known = {f.name for f in fields(cls)} - {"problems"}
        for key, val in raw.items():
            if key not in known:
                theme.problems.append(f"{key}: unknown key (ignored)")
            elif key in _GROUPS:
                theme._load_group(key, val)
            elif key == "sections":
                theme._load_sections(val)
            elif key == "palette":
                theme._load_palette(val)
            else:
                theme._load_leaf(theme, key, key, val)
        return theme

    def _load_leaf(self, target: Any, attr: str, path: str, val: Any) -> None:
        ok, want = _VALIDATORS[path]
        if ok(val):
            setattr(target, attr, val)
        else:
            self.problems.append(f"{path}: expected {want}, got {val!r}; using {getattr(target, attr)!r}")

    def _load_group(self, name: str, val: Any) -> None:
        if not isinstance(val, dict):
            self.problems.append(f"{name}: expected an object, got {val!r}")
            return
        group = getattr(self, name)
        names = {f.name for f in fields(group)}
        for key, v in val.items():
            if key not in names:
                self.problems.append(f"{name}.{key}: unknown key (ignored)")
            else:
                self._load_leaf(group, key, f"{name}.{key}", v)

    def _load_palette(self, val: Any) -> None:
        problems = palette_problems(val)
        self.problems.extend(problems)
        if isinstance(val, dict) or not problems:
            self.palette = copy.deepcopy(val)  # bad roles in an object are skipped by resolve()

    def _load_sections(self, val: Any) -> None:
        if not isinstance(val, list):
            self.problems.append(f"sections: expected a list of section ids, got {val!r}")
            return
        out: list[str] = []
        for item in val:
            if not isinstance(item, str):
                self.problems.append(f"sections: ignoring non-string entry {item!r}")
            elif item not in out:
                out.append(item)
        self.sections = out  # unknown ids are fine: the shell skips ids it has no component for

    def to_dict(self) -> dict:
        """The effective theme in file form (what theme.json would contain), colours as written."""
        out: dict[str, Any] = {}
        for f in fields(self):
            if f.name == "problems":
                continue
            v = getattr(self, f.name)
            out[f.name] = {g.name: getattr(v, g.name) for g in fields(v)} if f.name in _GROUPS else copy.deepcopy(v)
        return out

    def snapshot(self, palette: Palette | None = None, source: str = "") -> dict:
        """The dict published as `theme` in state.json: to_dict() with colours as #AARRGGBB (null
        when unset), plus `colors` (the resolved palette roles) and `palette_source`."""
        d = self.to_dict()
        if palette is None:
            palette, source = resolve(self.palette, None, "", True)
        for key in ("background", "accent_override"):
            d[key] = parse_color(d[key]) if d[key] else None
        for key in ("color", "off_task_color"):
            d["border"][key] = parse_color(d["border"][key]) if d["border"][key] else None
        d["colors"] = palette.to_dict()
        d["palette_source"] = source
        return d


def set_dotted(raw: dict, key: str, value: Any) -> dict:
    """Return a copy of `raw` with the dotted path `key` set to `value` (e.g. 'autohide.enabled')."""
    out = copy.deepcopy(raw)
    parts = key.split(".")
    node = out
    for p in parts[:-1]:
        nxt = node.setdefault(p, {})
        if not isinstance(nxt, dict):
            raise ValueError(f"{p!r} in {key!r} is not an object")
        node = nxt
    node[parts[-1]] = value
    return out


class ThemeService:
    """Owns the effective ThemeConfig and the resolved palette; the theme file is the source of truth.

    `on_change` fires after the theme or the palette changed (publish the snapshot); `log` records
    problems. `palette_source` supplies the desktop's Material colours (None: built-ins only).
    """

    def __init__(self, doc: JsonDocument, on_change: Callable[[], None],
                 log: Callable[..., None] = lambda kind, **data: None,
                 palette_source: PaletteSource | None = None) -> None:
        self.doc = doc
        self.on_change = on_change
        self.log = log
        self.palette_source = palette_source
        self.theme = ThemeConfig()
        self.palette, self.palette_from = self._resolve()

    def _resolve(self) -> tuple[Palette, str]:
        src = self.palette_source
        if src is None:
            return resolve(self.theme.palette, None, "", True)
        found = src.material()
        material, origin = found if found else (None, "")
        return resolve(self.theme.palette, material, origin, src.prefers_dark())

    def refresh_palette(self) -> None:
        """Re-read the desktop palette (the source changed); publish only if the colours changed."""
        new = self._resolve()
        if new != (self.palette, self.palette_from):
            self.palette, self.palette_from = new
            self.log("palette", source=self.palette_from)
            self.on_change()

    def load(self) -> None:
        """(Re)read the file. A corrupt file keeps the previous theme."""
        try:
            raw = self.doc.read()
        except (ValueError, OSError) as e:
            self.log("theme_error", error=str(e))
            return
        self.apply(raw)

    def apply(self, raw: Any) -> None:
        old = self.theme
        self.theme = ThemeConfig.from_dict(raw)
        self.palette, self.palette_from = self._resolve()
        if self.theme.problems and self.theme.problems != old.problems:
            self.log("theme_error", error="; ".join(self.theme.problems))
        self.on_change()

    def on_file_error(self, e: Exception) -> None:
        self.log("theme_error", error=str(e))

    def snapshot(self) -> dict:
        return self.theme.snapshot(self.palette, self.palette_from)

    # ---------- control commands ----------
    def get(self, _arg: Any = None) -> dict:
        """The effective theme (file form), the resolved palette and its source, and any problems."""
        return {"theme": self.theme.to_dict(), "problems": list(self.theme.problems),
                "palette": {"source": self.palette_from, "colors": self.palette.to_dict()}}

    def set(self, arg: Any) -> str:
        """arg = {"key": "autohide.enabled", "value": true}. Rejected (nothing written) if invalid."""
        if not isinstance(arg, dict) or not isinstance(arg.get("key"), str) or "value" not in arg:
            raise ValueError('theme_set expects {"key": "<dotted.key>", "value": <json>}')
        raw = upgrade_v1(self.doc.read())
        new_raw = set_dotted(raw, arg["key"], arg["value"])
        before = set(ThemeConfig.from_dict(raw).problems)
        added = [p for p in ThemeConfig.from_dict(new_raw).problems if p not in before]
        if added:
            raise ValueError("rejected: " + "; ".join(added))
        self.doc.write(new_raw)
        self.apply(new_raw)
        return f"{arg['key']} = {arg['value']!r}"

    def reset(self, _arg: Any = None) -> str:
        """Overwrite the theme file with the defaults."""
        raw = ThemeConfig().to_dict()
        self.doc.write(raw)
        self.apply(raw)
        return "theme reset to defaults"
