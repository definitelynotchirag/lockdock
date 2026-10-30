"""The mascot pet: wires PetBrain to pet.json, the sprite packs, activity verdicts and the `pet` command."""
from __future__ import annotations

import json
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any

from ..adapters.claude_cli import ClaudeCliSpeaker, JsonFileCache
from ..adapters.json_config import PET_EXAMPLE, JsonConfigLoader
from ..adapters.pet_packs import BUILTIN_PETS_DIR, DirPetPacks
from ..core.pet import MOODS, SETTABLE, PetBrain, PetConfig, pet_config_from_dict, pet_setting
from ..paths import PET_CACHE_FILE, PET_FILE, USER_PETS_DIR

if TYPE_CHECKING:
    from ..core.daemon import Daemon

PET_ERRORS = (ValueError, KeyError, TypeError, OSError)
USAGE = ("usage: pet [status | calm | mood <" + "|".join(MOODS) + "|auto> | mute | unmute | pack <name> "
         "| packs | say <text> | set <key> <number> | on | off]")


class PetFeature:
    """Owns the pet's loader, brain and optional speaker; handles the `pet` control command."""

    def __init__(self, daemon: Daemon) -> None:
        self.daemon = daemon
        self.loader: JsonConfigLoader[PetConfig] = JsonConfigLoader(PET_FILE, PET_EXAMPLE,
                                                                    parse=pet_config_from_dict)
        try:
            cfg = self.loader.load()
        except PET_ERRORS as e:
            daemon.events.log("pet_config_error", error=str(e))
            cfg = PetConfig()
        self.packs = DirPetPacks([("user", USER_PETS_DIR), ("built-in", BUILTIN_PETS_DIR)])
        self.brain = PetBrain(cfg, self.packs, daemon.clock, daemon.publish)
        self._sync_speaker(cfg)

    def _sync_speaker(self, cfg: PetConfig) -> None:
        """Build the LLM speaker only once llm_lines is on (and the daemon's llm is enabled)."""
        if not (cfg.llm_lines and self.daemon.cfg.llm_enabled):
            self.brain.speaker = None
            return
        if self.brain.speaker is None:
            self.brain.speaker = ClaudeCliSpeaker(JsonFileCache(PET_CACHE_FILE), cfg.persona,
                                                  model=self.daemon.cfg.llm_model)
        speaker = self.brain.speaker
        if isinstance(speaker, ClaudeCliSpeaker):
            speaker.persona = cfg.persona
            speaker.model = self.daemon.cfg.llm_model

    def apply(self, cfg: PetConfig) -> None:
        self._sync_speaker(cfg)
        self.brain.apply_config(cfg)

    def on_error(self, e: Exception) -> None:
        self.daemon.events.log("pet_config_error", error=str(e))

    def _persist(self, **changes: Any) -> bool:
        try:
            self.apply(self.loader.update(changes))
        except PET_ERRORS as e:
            self.on_error(e)
            return False
        return True

    def set_value(self, args: list[str]) -> str:
        """`pet set <key> <json number>`: validate, write pet.json, apply live."""
        args = " ".join(args).split()
        if len(args) != 2:
            return f"usage: pet set <key> <number>  (keys: {', '.join(SETTABLE)})"
        key, text = args
        try:
            value = json.loads(text)
            changes = pet_setting(self.brain.cfg, key, value)
        except ValueError as e:   # json.JSONDecodeError is a ValueError
            return str(e)
        if not self._persist(**changes):
            return f"could not write {self.loader.path} (see lockdock log)"
        self.daemon.events.log("pet_set", key=key, value=value)
        return f"{key} = {value}"

    def handle(self, arg: Any) -> Any:
        """`pet` control command; `arg` is a list of words (or one string)."""
        args = arg.split(None, 1) if isinstance(arg, str) else [str(a) for a in (arg or [])]
        sub, rest = (args[0], " ".join(args[1:])) if args else ("status", "")
        b = self.brain
        if sub == "status":
            return b.snapshot()
        if sub == "calm":
            b.calm()
            return "calmed"
        if sub == "mood":
            try:
                b.force_mood(rest or "auto")
            except ValueError as e:
                return str(e)
            return f"mood {b.mood}" + (" (forced)" if b.forced else " (auto)")
        if sub in ("on", "off"):
            self._persist(enabled=sub == "on")
            return "pet on" if sub == "on" else "pet off (no sprite, lines or growth; `lockdock pet on` brings it back)"
        if sub in ("mute", "unmute"):
            b.set_muted(sub == "mute")
            self._persist(muted=sub == "mute")
            return "muted" if sub == "mute" else "unmuted"
        if sub == "pack":
            if not self.packs.resolve(rest):
                return f"no pack {rest!r} (see: lockdock pet packs)"
            self._persist(pack=rest)
            return f"pack {rest}"
        if sub == "packs":
            return self.packs.available()
        if sub == "set":
            return self.set_value(args[1:])
        if sub == "say":
            b.say(rest)
            return "said"
        return USAGE

    async def tick_loop(self) -> None:
        """Advance the brain once a second."""
        while True:
            await self.daemon.clock.sleep(1.0)
            self.brain.tick()


def install(daemon: Daemon) -> list[Awaitable[None]]:
    """Register the `pet` section and command; return the tick loop and the pet.json watcher."""
    pet = PetFeature(daemon)
    daemon.activity_listeners.append(pet.brain.on_activity)
    daemon.config_listeners.append(lambda _cfg: pet._sync_speaker(pet.brain.cfg))
    daemon.register_section("pet", pet.brain.snapshot)
    daemon.register_command("pet", pet.handle)
    return [pet.tick_loop(), pet.loader.watch(pet.apply, pet.on_error)]
