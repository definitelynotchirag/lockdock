"""Palette: the dock's colour roles, mapped from the desktop's Material You scheme or built in.

The desktop (end-4 / matugen) writes Material roles (primary, surface_container, ...) to a
colors.json; `Palette.from_material` turns them into the roles the dock draws with. When no
such file exists, `DARK` or `LIGHT` is used, picked by the desktop's colour-scheme preference.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, fields, replace
from typing import Any

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



ROLES = ("bg", "bg_elevated", "surface", "surface_hover", "text", "text_muted", "outline", "accent",
         "on_accent", "accent_container", "on_accent_container", "secondary", "tertiary", "danger",
         "on_danger", "success", "warning", "bubble", "bubble_text", "shadow")
PALETTE_NAMES = ("system", "dark", "light")


@dataclass(frozen=True)
class Palette:
    """Dock colour roles as '#AARRGGBB'.

    bg: island / card fill; bg_elevated: the slab card and the nudge's lift; surface: chips at rest;
    surface_hover: hovered pills, chips; text / text_muted: labels and glyphs; outline: hairline
    borders; accent (+ on_accent): focused app pill, countdown, badges; accent_container (+ on_):
    the active mode pill; danger (+ on_danger): off task; success / warning: agent state dots;
    bubble / bubble_text: the pet's speech bubble; shadow: island drop shadows.
    """
    bg: str
    bg_elevated: str
    surface: str
    surface_hover: str
    text: str
    text_muted: str
    outline: str
    accent: str
    on_accent: str
    accent_container: str
    on_accent_container: str
    secondary: str
    tertiary: str
    danger: str
    on_danger: str
    success: str
    warning: str
    bubble: str
    bubble_text: str
    shadow: str

    def __post_init__(self) -> None:
        for f in fields(self):
            c = parse_color(getattr(self, f.name))
            if c is None:
                raise ValueError(f"palette role {f.name}: bad colour {getattr(self, f.name)!r}")
            object.__setattr__(self, f.name, c)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    def merged(self, overrides: dict[str, str]) -> Palette:
        """A copy with some roles replaced (keys must be ROLES, values colours)."""
        return replace(self, **overrides)

    @property
    def dark(self) -> bool:
        return luminance(self.bg) < 0.5

    @classmethod
    def from_material(cls, roles: dict[str, Any], dark: bool) -> Palette:
        """Map Material You roles to dock roles. Missing or invalid roles come from DARK / LIGHT."""
        base = DARK if dark else LIGHT

        def m(*names: str) -> str | None:
            for n in names:
                c = parse_color(roles.get(n))
                if c is not None:
                    return c
            return None

        surface = m("surface_container_highest", "surface_variant")
        on_surface = m("on_surface", "on_background")
        hover = mix(surface, on_surface, 0.10) if surface and on_surface else None
        picked = {
            "bg": m("surface_container", "surface", "background"),
            "bg_elevated": m("surface_container_high", "surface_container", "surface"),
            "surface": surface,
            "surface_hover": hover,
            "text": on_surface,
            "text_muted": m("on_surface_variant"),
            "outline": m("outline_variant", "outline"),
            "accent": m("primary"),
            "on_accent": m("on_primary"),
            "accent_container": m("primary_container"),
            "on_accent_container": m("on_primary_container"),
            "secondary": m("secondary"),
            "tertiary": m("tertiary"),
            "danger": m("error"),
            "on_danger": m("on_error"),
            "bubble": m("inverse_surface"),
            "bubble_text": m("inverse_on_surface"),
            "shadow": m("shadow", "scrim"),
        }
        return base.merged({k: v for k, v in picked.items() if v is not None})


def luminance(color: str) -> float:
    """Relative luminance (0 black .. 1 white) of a '#AARRGGBB' / '#RRGGBB' colour."""
    c = parse_color(color) or "#FF000000"
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (3, 5, 7))
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def mix(a: str, b: str, t: float) -> str:
    """Blend opaque colour b over a with weight t (0 = a, 1 = b); alpha from a."""
    ca, cb = parse_color(a) or "#FF000000", parse_color(b) or "#FF000000"
    ch = [ca[1:3]] + [f"{round(int(ca[i:i + 2], 16) * (1 - t) + int(cb[i:i + 2], 16) * t):02X}" for i in (3, 5, 7)]
    return "#" + "".join(ch)


DARK = Palette(
    bg="#1D2024", bg_elevated="#272A2F", surface="#32353A", surface_hover="#3E4146",
    text="#E0E2E8", text_muted="#C2C7CE", outline="#42474E",
    accent="#99CCFA", on_accent="#003350", accent_container="#084B72", on_accent_container="#CDE5FF",
    secondary="#B8C8DA", tertiary="#D2BFE7", danger="#FFB4AB", on_danger="#690005",
    success="#8FD5A6", warning="#F2C46B", bubble="#E0E2E8", bubble_text="#2D3135", shadow="#000000",
)
LIGHT = Palette(
    bg="#EBEEF3", bg_elevated="#E6E8EE", surface="#E0E2E8", surface_hover="#CDD0D5",
    text="#181C20", text_muted="#42474E", outline="#C2C7CE",
    accent="#2C638B", on_accent="#FFFFFF", accent_container="#CDE5FF", on_accent_container="#001D31",
    secondary="#51606F", tertiary="#67587A", danger="#BA1A1A", on_danger="#FFFFFF",
    success="#2F7D4F", warning="#8A5A00", bubble="#2D3135", bubble_text="#EEF1F6", shadow="#000000",
)
_SUCCESS_WARNING = {True: (DARK.success, DARK.warning), False: (LIGHT.success, LIGHT.warning)}


def resolve(spec: Any, material: dict[str, Any] | None, origin: str, prefers_dark: bool) -> tuple[Palette, str]:
    """The palette for theme.json's `palette` value, and a human-readable source.

    spec: "system" (Material file, else the built-in matching `prefers_dark`), "dark", "light",
    or {role: colour, ..., "base": "system"|"dark"|"light"} (roles merged over the base).
    `material` is the parsed colors.json (None if missing), `origin` its path.
    """
    overrides: dict[str, str] = {}
    base_name = spec if isinstance(spec, str) else "system"
    if isinstance(spec, dict):
        base_name = spec.get("base", "system")
        overrides = {k: v for k, v in spec.items() if k in ROLES and parse_color(v) is not None}
    if base_name == "dark":
        pal, src = DARK, "built-in dark"
    elif base_name == "light":
        pal, src = LIGHT, "built-in light"
    elif material:
        surface = parse_color(material.get("surface") or material.get("background"))
        dark = luminance(surface) < 0.5 if surface else prefers_dark
        pal, src = Palette.from_material(material, dark), f"{origin} ({'dark' if dark else 'light'})"
        success, warning = _SUCCESS_WARNING[dark]
        pal = pal.merged({"success": success, "warning": warning})
    else:
        pal = DARK if prefers_dark else LIGHT
        src = f"fallback built-in {'dark' if prefers_dark else 'light'} (no colors.json; color-scheme)"
    if overrides:
        pal = pal.merged(overrides)
        src += f" + {len(overrides)} override{'s' if len(overrides) > 1 else ''}"
    return pal, src


def palette_problems(spec: Any) -> list[str]:
    """Problems in theme.json's `palette` value (empty when valid)."""
    if isinstance(spec, str):
        return [] if spec in PALETTE_NAMES else [f"palette: expected one of {PALETTE_NAMES} or an object, got {spec!r}"]
    if not isinstance(spec, dict):
        return [f"palette: expected one of {PALETTE_NAMES} or an object, got {spec!r}"]
    out = []
    for k, v in spec.items():
        if k == "base":
            if v not in PALETTE_NAMES:
                out.append(f"palette.base: expected one of {PALETTE_NAMES}, got {v!r}")
        elif k not in ROLES:
            out.append(f"palette.{k}: unknown role (ignored); roles: {', '.join(ROLES)}")
        elif parse_color(v) is None:
            out.append(f"palette.{k}: expected a colour, got {v!r} (ignored)")
    return out
