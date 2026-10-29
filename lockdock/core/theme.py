"""Theme: every visual knob of the dock, validated, with defaults that match the shipped look."""
from __future__ import annotations

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from typing import Any

from .ports import JsonDocument

POSITIONS = ("bottom", "top")
DEFAULT_SECTIONS = ("pet", "modes", "apps", "agents", "held")

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_FUNC = re.compile(r"^(rgba?)\(\s*([^)]*)\)$", re.IGNORECASE)


def parse_color(value: Any) -> str | None:
    """Normalise '#RRGGBB', '#AARRGGBB', 'rgb(...)' or 'rgba(...)' to '#AARRGGBB' (None if invalid).

    rgb channels are 0..1 floats, or 0..255 when any channel is above 1; alpha is 0..1.
    """
    if not isinstance(value, str):
        return None
    s = value.strip()
    if _HEX.match(s):
        return ("#FF" + s[1:] if len(s) == 7 else s).upper()
    m = _FUNC.match(s)
    if not m:
        return None
    try:
        parts = [float(p) for p in m.group(2).split(",")]
    except ValueError:
        return None
    if len(parts) != (4 if m.group(1).lower() == "rgba" else 3):
        return None
    rgb, alpha = parts[:3], parts[3] if len(parts) == 4 else 1.0
    if any(c < 0 for c in rgb) or not 0 <= alpha <= 1:
        return None
    if any(c > 1 for c in rgb):
        if any(c > 255 for c in rgb):
            return None
        rgb = [c / 255 for c in rgb]
    ch = [int(c * 255 + 0.5) for c in (alpha, *rgb)]
    return "#" + "".join(f"{c:02X}" for c in ch)


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


@dataclass
class BorderTheme:
    """Card border: normal colour, width in px, and the colour while off task."""
    color: str = "rgba(1,1,1,0.12)"
    width: float = 1
    off_task_color: str = "rgba(1,0.35,0.3,0.8)"


@dataclass
class FontTheme:
    """Font family ("" = system default) and base size in px."""
    family: str = ""
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


_VALIDATORS: dict[str, tuple[Callable[[Any], bool], str]] = {
    "position": (lambda v: v in POSITIONS, '"bottom" or "top"'),
    "margin": (_num(0, 1000), "a number 0..1000"),
    "scale": (_num(0.3, 4), "a number 0.3..4"),
    "radius": (_num(0, 200), "a number 0..200"),
    "background": (_is_color, "#AARRGGBB, #RRGGBB or rgba(r,g,b,a)"),
    "accent_override": (lambda v: v is None or _is_color(v), "null or a colour"),
    "icon_size": (_num(8, 256), "a number 8..256"),
    "show_unpinned": (_is_bool, "true or false"),
    "opacity": (_num(0, 1), "a number 0..1"),
    "border.color": (_is_color, "a colour"),
    "border.width": (_num(0, 50), "a number 0..50"),
    "border.off_task_color": (_is_color, "a colour"),
    "font.family": (_is_str, "a string"),
    "font.size": (_num(4, 100), "a number 4..100"),
    "autohide.enabled": (_is_bool, "true or false"),
    "autohide.reveal_px": (_int(1, 100), "an integer 1..100"),
    "autohide.hide_delay_ms": (_int(0, 600000), "an integer 0..600000"),
    "nudge.enabled": (_is_bool, "true or false"),
}
_GROUPS = ("border", "font", "autohide", "nudge")


@dataclass
class ThemeConfig:
    """The dock's look. `from_dict` never raises: bad values fall back to the default and are
    listed in `problems`. `snapshot()` is what the shell reads as `st.theme`."""
    position: str = "bottom"
    margin: float = 10
    scale: float = 1.0
    radius: float = 22
    background: str = "rgba(0.11,0.11,0.13,0.86)"
    border: BorderTheme = field(default_factory=BorderTheme)
    accent_override: str | None = None
    font: FontTheme = field(default_factory=FontTheme)
    icon_size: float = 36
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
            out[f.name] = {g.name: getattr(v, g.name) for g in fields(v)} if f.name in _GROUPS else copy.copy(v)
        return out

    def snapshot(self) -> dict:
        """The dict published as `theme` in state.json: to_dict() with colours as #AARRGGBB."""
        d = self.to_dict()
        d["background"] = parse_color(d["background"])
        d["accent_override"] = parse_color(d["accent_override"]) if d["accent_override"] else None
        d["border"]["color"] = parse_color(d["border"]["color"])
        d["border"]["off_task_color"] = parse_color(d["border"]["off_task_color"])
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
    """Owns the effective ThemeConfig; the theme file is the source of truth.

    `on_change` fires after the theme changed (publish the snapshot); `log` records problems.
    """

    def __init__(self, doc: JsonDocument, on_change: Callable[[], None],
                 log: Callable[..., None] = lambda kind, **data: None) -> None:
        self.doc = doc
        self.on_change = on_change
        self.log = log
        self.theme = ThemeConfig()

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
        if self.theme.problems and self.theme.problems != old.problems:
            self.log("theme_error", error="; ".join(self.theme.problems))
        self.on_change()

    def on_file_error(self, e: Exception) -> None:
        self.log("theme_error", error=str(e))

    def snapshot(self) -> dict:
        return self.theme.snapshot()

    # ---------- control commands ----------
    def get(self, _arg: Any = None) -> dict:
        """The effective theme (file form) and any problems found in the file."""
        return {"theme": self.theme.to_dict(), "problems": list(self.theme.problems)}

    def set(self, arg: Any) -> str:
        """arg = {"key": "autohide.enabled", "value": true}. Rejected (nothing written) if invalid."""
        if not isinstance(arg, dict) or not isinstance(arg.get("key"), str) or "value" not in arg:
            raise ValueError('theme_set expects {"key": "<dotted.key>", "value": <json>}')
        raw = self.doc.read()
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
