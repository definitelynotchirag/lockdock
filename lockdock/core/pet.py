"""The mascot pet: a mood that follows how long you have been off task, a speech line, and growth."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .ports import Clock, PetPackSource, Speaker
from .tasks import Spawn, spawn_task

MOODS: tuple[str, ...] = ("content", "suspicious", "annoyed", "furious")
MAX_TICK_S = 5.0  # a longer gap (suspend, stalled loop) counts as this much

DEFAULT_PERSONA = ("A small round grey cat who adores your focus, is wildly dramatic about distractions "
                   "and speaks in short lowercase sentences.")
DEFAULT_THRESHOLDS: Mapping[str, float] = MappingProxyType({"suspicious": 45.0, "annoyed": 120.0, "furious": 300.0})
DEFAULT_LINES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "content": (
        "purr. this is the good stuff.",
        "{mode} mode, going great. I approve.",
        "*slow blink* that means I respect you.",
        "I'll nap right here while you work.",
        "focus smells like tuna. keep going.",
    ),
    "suspicious": (
        "hmm. {app}? in {mode} mode?",
        "my whiskers are twitching about this {app} thing.",
        "I'm watching {app}. very. closely.",
        "is \"{title}\" part of {mode}? asking for a cat.",
        "that tab looks like a cardboard box. tempting. still no.",
    ),
    "annoyed": (
        "{app} again. my tail is thrashing.",
        "this is not {mode}. this is {app}.",
        "I knocked a glass off the desk because of {app}.",
        "I nap less than you've been on {app}.",
        "the judge says: {reason}. I agree, loudly.",
    ),
    "furious": (
        "HISS. {app} is NOT {mode}.",
        "I am getting bigger. close {app} and I shrink.",
        "every second of {app} makes me larger.",
        "I will sit on your screen until {mode} happens.",
        "MEOW. {reason}. BACK. TO. {mode}.",
    ),
})


@dataclass
class PetConfig:
    """pet.json, parsed. Missing keys take these defaults."""

    name: str = ""                       # "" = the pack's name
    pack: str = "cat"
    persona: str = DEFAULT_PERSONA
    thresholds: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    decay_per_s: float = 2.0             # off_seconds lost per second while on task / neutral
    grow_s: float = 240.0                # seconds of furious to reach full size
    shrink_s: float = 4.0                # seconds to shrink from full size back to the dock
    max_scale: float = 24.0              # full size, in dock sprites (the overlay caps it at the fraction below)
    max_screen_fraction: float = 0.9     # the overlay never gets taller than this share of the screen
    nag_every_s: float = 60.0            # a fresh line this often while off task
    lines: dict[str, list[str]] = field(default_factory=lambda: {m: list(v) for m, v in DEFAULT_LINES.items()})
    llm_lines: bool = False
    muted: bool = False
    position: str = "left"               # left | right of the mode strip


# lower bounds of the timing keys (pet.json values below them are raised to them; `pet set` rejects them)
TIMING_MIN: Mapping[str, float] = MappingProxyType(
    {"decay_per_s": 0.0, "grow_s": 1.0, "shrink_s": 0.1, "nag_every_s": 5.0, "max_scale": 1.0})
SETTABLE: tuple[str, ...] = tuple(f"thresholds.{m}" for m in MOODS[1:]) + tuple(TIMING_MIN)


def pet_setting(cfg: PetConfig, key: str, value: object) -> dict[str, Any]:
    """The pet.json changes for `pet set <key> <value>` (a number of seconds, or of sprites for
    max_scale). Thresholds stay in order: suspicious <= annoyed <= furious. Raises ValueError."""
    if key not in SETTABLE:
        raise ValueError(f"unknown pet setting {key!r} (one of {', '.join(SETTABLE)})")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number, not {value!r}")
    v = float(value)
    if key.startswith("thresholds."):
        if v < 0:
            raise ValueError(f"{key} must be 0 or more")
        t = {**DEFAULT_THRESHOLDS, **cfg.thresholds, key.split(".", 1)[1]: v}
        if not t["suspicious"] <= t["annoyed"] <= t["furious"]:
            raise ValueError("thresholds must stay in order: suspicious <= annoyed <= furious")
        return {"thresholds": {m: _plain(x) for m, x in t.items()}}
    if v < TIMING_MIN[key]:
        raise ValueError(f"{key} must be {TIMING_MIN[key]:g} or more")
    return {key: _plain(v)}


def _plain(v: float) -> float | int:
    """45.0 -> 45, so pet.json stays as people write it."""
    return int(v) if v.is_integer() else v


def pet_config_from_dict(raw: dict) -> PetConfig:
    """Build a PetConfig from parsed pet.json. Raises ValueError/TypeError on bad values."""
    d = PetConfig()
    thresholds = {**d.thresholds, **{k: float(v) for k, v in (raw.get("thresholds") or {}).items()}}
    lines = {**d.lines, **{k: [str(x) for x in v] for k, v in (raw.get("lines") or {}).items() if v}}
    position = raw.get("position", d.position)
    return PetConfig(
        name=str(raw.get("name", d.name)), pack=str(raw.get("pack", d.pack)),
        persona=str(raw.get("persona", d.persona)), thresholds=thresholds,
        decay_per_s=max(TIMING_MIN["decay_per_s"], float(raw.get("decay_per_s", d.decay_per_s))),
        grow_s=max(TIMING_MIN["grow_s"], float(raw.get("grow_s", d.grow_s))),
        shrink_s=max(TIMING_MIN["shrink_s"], float(raw.get("shrink_s", d.shrink_s))),
        max_scale=max(TIMING_MIN["max_scale"], float(raw.get("max_scale", d.max_scale))),
        max_screen_fraction=min(1.0, max(0.05, float(raw.get("max_screen_fraction", d.max_screen_fraction)))),
        nag_every_s=max(TIMING_MIN["nag_every_s"], float(raw.get("nag_every_s", d.nag_every_s))),
        lines=lines, llm_lines=bool(raw.get("llm_lines", d.llm_lines)), muted=bool(raw.get("muted", d.muted)),
        position=position if position in ("left", "right") else "left",
    )


class _Keep(dict):
    """format_map helper: unknown {fields} stay as written."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render_line(template: str, ctx: Mapping[str, str]) -> str:
    """Fill {app} {mode} {reason} {title}; a malformed template comes back unchanged."""
    try:
        return template.format_map(_Keep(ctx))
    except (ValueError, IndexError, AttributeError):
        return template


class PetBrain:
    """Turns activity verdicts and a 1 s tick into the pet's mood, size and speech line.

    `off_seconds` grows while the latest verdict is off and decays `decay_per_s` times
    as fast otherwise; the mood comes from `thresholds`. Once furious and still off task,
    `growth` (0..1) rises over `grow_s`; otherwise it falls over `shrink_s`. `scale` is
    1 + growth * (max_scale - 1) dock sprites. Lines are picked per mood change and every
    `nag_every_s` while off task; with `llm_lines` a Speaker may replace a fresh line.
    """

    def __init__(self, config: PetConfig, packs: PetPackSource, clock: Clock, on_change: Callable[[], None],
                 speaker: Speaker | None = None, spawn: Spawn = spawn_task) -> None:
        self.packs = packs
        self.clock = clock
        self.on_change = on_change
        self.speaker = speaker
        self.spawn = spawn
        self.cfg = config
        self.pack_dir = ""
        self.manifest: dict = {}
        self.verdict = "neutral"
        self.ctx: dict[str, str] = {"app": "", "title": "", "reason": "", "mode": ""}
        self.off_seconds = 0.0
        self.growth = 0.0
        self.forced: str | None = None
        self.line = ""
        self.line_id = 0
        self._mood = "content"
        self._last_tick = clock.now()
        self._last_line_at = clock.now()
        self._next_line: dict[str, int] = {}
        self._published: tuple = ()
        self._resolve_pack()
        self._published = self._key()

    # ---------- inputs ----------
    def apply_config(self, cfg: PetConfig) -> None:
        """A new pet.json (hot reload)."""
        self.cfg = cfg
        self._resolve_pack()
        if cfg.muted:
            self.line = ""
        self._update(speak=False)

    def on_activity(self, activity: Mapping[str, Any]) -> None:
        """A verdict from the daemon: {verdict, reason, app, title, mode}."""
        self.verdict = str(activity.get("verdict") or "neutral")
        app = str(activity.get("app") or "")
        self.ctx = {"app": app.rsplit(".", 1)[-1] if " " not in app else app,  # dev.zed.Zed -> Zed
                    "title": str(activity.get("title") or "")[:60],
                    "reason": str(activity.get("reason") or ""), "mode": str(activity.get("mode") or "")}

    def tick(self) -> None:
        """Advance the clocks; call about once a second."""
        now = self.clock.now()
        dt = min(MAX_TICK_S, max(0.0, now - self._last_tick))
        self._last_tick = now
        if self.verdict == "off":
            self.off_seconds += dt
        else:
            self.off_seconds = max(0.0, self.off_seconds - self.cfg.decay_per_s * dt)
        mood = self.mood
        if self.forced == "furious" and not self.cfg.muted:
            self.growth = 1.0
        elif mood == "furious" and self.verdict == "off" and not self.cfg.muted:
            self.growth = min(1.0, self.growth + dt / self.cfg.grow_s)
        else:
            self.growth = max(0.0, self.growth - dt / self.cfg.shrink_s)
        nag = (self.verdict == "off" and mood != "content"
               and now - self._last_line_at >= self.cfg.nag_every_s)
        self._update(speak=True, nag=nag)

    # ---------- commands ----------
    def calm(self) -> None:
        """Forget everything: content, dock size, no line, no forced mood."""
        self.off_seconds = 0.0
        self.growth = 0.0
        self.forced = None
        self._mood = "content"
        self.line = ""
        self._update(speak=False)

    def force_mood(self, mood: str | None) -> None:
        """Preview a mood (furious also jumps to full size); None or "auto" returns to the computed mood."""
        if mood in (None, "", "auto"):
            self.forced = None
        elif mood in MOODS:
            self.forced = mood
            self.growth = 1.0 if mood == "furious" and not self.cfg.muted else 0.0
        else:
            raise ValueError(f"unknown mood {mood!r} (one of {', '.join(MOODS)}, auto)")
        self._update(speak=True)

    def say(self, text: str) -> None:
        """Show `text` as the speech line now."""
        self._set_line(text)
        self._update(speak=False)

    def set_muted(self, muted: bool) -> None:
        self.cfg.muted = muted
        if muted:
            self.line = ""
        self._update(speak=False)

    # ---------- derived state ----------
    @property
    def mood(self) -> str:
        if self.forced:
            return self.forced
        t = self.cfg.thresholds
        for m in ("furious", "annoyed", "suspicious"):
            if self.off_seconds >= t.get(m, DEFAULT_THRESHOLDS[m]):
                return m
        return "content"

    @property
    def scale(self) -> float:
        return round(1.0 + self.growth * (self.cfg.max_scale - 1.0), 2)

    def snapshot(self) -> dict:
        """The `pet` section of state.json."""
        manifest = self.manifest
        return {"name": self.cfg.name or manifest.get("name", self.cfg.pack), "mood": self._mood,
                "scale": self.scale, "line": self.line, "line_id": self.line_id,
                "off_seconds": int(self.off_seconds), "pack": self.cfg.pack, "pack_dir": self.pack_dir,
                "manifest": manifest, "size": int(manifest.get("size", 48)), "muted": self.cfg.muted,
                "forced": self.forced, "position": self.cfg.position,
                "max_screen_fraction": self.cfg.max_screen_fraction, "config": self._timings()}

    def _timings(self) -> dict:
        """The effective timing values (`st.pet.config`), for the quick settings rows."""
        c = self.cfg
        return {"thresholds": {m: c.thresholds.get(m, DEFAULT_THRESHOLDS[m]) for m in MOODS[1:]},
                "grow_s": c.grow_s, "shrink_s": c.shrink_s, "decay_per_s": c.decay_per_s,
                "nag_every_s": c.nag_every_s, "max_scale": c.max_scale}

    # ---------- internals ----------
    def _resolve_pack(self) -> None:
        found = self.packs.resolve(self.cfg.pack) or self.packs.resolve("cat")
        self.pack_dir, self.manifest = found if found else ("", {})

    def _key(self) -> tuple:
        return (self._mood, self.scale, self.line, self.line_id, int(self.off_seconds), self.cfg.pack,
                self.pack_dir, self.cfg.muted, self.forced, self.cfg.position, self.cfg.max_screen_fraction,
                self.cfg.name, repr(self._timings()))

    def _update(self, speak: bool, nag: bool = False) -> None:
        mood = self.mood
        changed_mood = mood != self._mood
        self._mood = mood
        if speak and (changed_mood or nag) and not self.cfg.muted:
            self._speak(mood, ask_llm=changed_mood)
        key = self._key()
        if key != self._published:
            self._published = key
            self.on_change()

    def _set_line(self, text: str) -> None:
        self.line = text
        self.line_id += 1
        self._last_line_at = self.clock.now()

    def _speak(self, mood: str, ask_llm: bool) -> None:
        options = self.cfg.lines.get(mood) or list(DEFAULT_LINES[mood])
        i = self._next_line.get(mood, 0)
        self._next_line[mood] = i + 1
        self._set_line(render_line(options[i % len(options)], self.ctx))
        if ask_llm and mood != "content" and self.cfg.llm_lines and self.speaker is not None:
            self.spawn(self._ask_speaker(mood, self.line_id))

    async def _ask_speaker(self, mood: str, line_id: int) -> None:
        assert self.speaker is not None
        c = self.ctx
        text = await self.speaker.line(mood, c["mode"], c["app"], c["title"], c["reason"])
        if text and self.line_id == line_id and self._mood == mood and not self.cfg.muted:
            self.line = text.strip()
            self._published = self._key()
            self.on_change()
