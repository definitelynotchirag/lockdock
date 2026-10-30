import json
from pathlib import Path

import pytest

from lockdock.adapters.json_config import PET_EXAMPLE, JsonConfigLoader
from lockdock.adapters.pet_packs import BUILTIN_PETS_DIR, DirPetPacks
from lockdock.core.daemon import Daemon
from lockdock.core.models import WindowInfo
from lockdock.core.pet import (DEFAULT_LINES, MOODS, PetBrain, PetConfig, pet_config_from_dict, pet_setting,
                               render_line)

from .fakes import (FakeClassifier, FakeClock, FakeConfigSource, FakePetPacks, FakePublisher, FakeRunner,
                    FakeSink, FakeSpeaker, Spawner, make_config)

OFF = {"verdict": "off", "app": "YouTube", "title": "cats compilation", "reason": "video", "mode": "Writing"}
ON = {"verdict": "on", "app": "Obsidian", "title": "draft", "reason": "mode app", "mode": "Writing"}


class Rig:
    """A PetBrain on a fake clock, counting on_change calls."""

    def __init__(self, cfg: PetConfig | None = None, speaker=None, packs=None) -> None:
        self.clock = FakeClock()
        self.changes = 0
        self.spawner = Spawner()
        self.brain = PetBrain(cfg or PetConfig(), packs or FakePetPacks(), self.clock, self._changed,
                              speaker=speaker, spawn=self.spawner)

    def _changed(self) -> None:
        self.changes += 1

    def run(self, seconds: int, activity: dict | None = None) -> None:
        if activity is not None:
            self.brain.on_activity(activity)
        for _ in range(seconds):
            self.clock.t += 1
            self.brain.tick()


def test_config_defaults_and_example():
    d = pet_config_from_dict({})
    assert d == PetConfig()
    assert d.thresholds == {"suspicious": 45, "annoyed": 120, "furious": 300}
    assert (d.decay_per_s, d.grow_s, d.shrink_s, d.max_screen_fraction, d.nag_every_s) == (2, 240, 4, 0.9, 60)
    assert d.pack == "cat" and d.position == "left" and not d.muted and not d.llm_lines
    part = pet_config_from_dict({"thresholds": {"furious": 90}, "lines": {"content": ["hi"]}, "position": "up"})
    assert part.thresholds == {"suspicious": 45, "annoyed": 120, "furious": 90}
    assert part.lines["content"] == ["hi"] and part.lines["furious"] == list(DEFAULT_LINES["furious"])
    assert part.position == "left"
    example = json.loads(PET_EXAMPLE.read_text())
    assert pet_config_from_dict(example) == PetConfig()
    assert all(len(example["lines"][m]) == 5 for m in MOODS)
    with pytest.raises(ValueError):
        pet_config_from_dict({"grow_s": "slow"})


def test_loader_seeds_and_updates(tmp_path):
    loader = JsonConfigLoader(tmp_path / "pet.json", PET_EXAMPLE, parse=pet_config_from_dict)
    assert loader.load().pack == "cat" and (tmp_path / "pet.json").exists()
    cfg = loader.update({"pack": "dog", "muted": True})
    assert cfg.pack == "dog" and cfg.muted
    assert json.loads((tmp_path / "pet.json").read_text())["lines"]["furious"][0].startswith("HISS")


def test_mood_thresholds():
    r = Rig()
    r.run(44, OFF)
    assert r.brain.mood == "content"
    r.run(1)
    assert r.brain.mood == "suspicious"
    r.run(74)
    assert r.brain.mood == "suspicious"
    r.run(1)
    assert r.brain.mood == "annoyed"
    r.run(180)
    assert r.brain.mood == "furious" and r.brain.snapshot()["off_seconds"] == 300


def test_decay_is_faster_than_growth():
    r = Rig()
    r.run(100, OFF)
    assert r.brain.mood == "suspicious"
    r.run(20, ON)
    assert r.brain.off_seconds == 60 and r.brain.mood == "suspicious"
    r.run(10, {**ON, "verdict": "neutral"})
    assert r.brain.off_seconds == 40 and r.brain.mood == "content"
    r.run(100)
    assert r.brain.off_seconds == 0


def test_growth_and_shrink():
    r = Rig()
    r.run(299, OFF)
    assert r.brain.scale == 1.0
    r.run(121)  # furious from second 300: 121 s of growth
    assert r.brain.growth == pytest.approx(121 / 240)
    assert r.brain.scale == round(1 + 121 / 240 * 23, 2)
    r.run(200)
    assert r.brain.growth == 1.0 and r.brain.scale == 24.0
    r.run(2, ON)
    assert r.brain.growth == pytest.approx(0.5)
    r.run(2)
    assert r.brain.growth == 0 and r.brain.scale == 1.0
    assert r.brain.mood == "furious"  # mood calms slowly, size snaps back fast


def test_long_gap_counts_as_a_short_tick():
    r = Rig()
    r.brain.on_activity(OFF)
    r.clock.t += 1000  # suspend / stalled loop
    r.brain.tick()
    assert r.brain.off_seconds == 5


def test_nag_cadence_and_rotation():
    r0 = Rig(PetConfig(nag_every_s=10))
    r0.run(30, OFF)
    assert r0.brain.mood == "content" and r0.brain.line == ""
    r = Rig()
    r.run(44, OFF)
    assert r.brain.line == "" and r.brain.line_id == 0  # no nagging while still content
    r.run(1)
    assert r.brain.line_id == 1 and r.brain.line == "hmm. YouTube? in Writing mode?"
    r.run(59)
    assert r.brain.line_id == 1
    r.run(1)  # 60 s after the last line
    assert r.brain.line_id == 2 and "whiskers" in r.brain.line
    r.run(15)  # annoyed at 120 s: a mood change speaks at once and restarts the nag timer
    assert r.brain.mood == "annoyed" and r.brain.line_id == 3 and r.brain.line.startswith("YouTube again")
    r.run(59)
    assert r.brain.line_id == 3
    r.run(1)
    assert r.brain.line_id == 4
    r.run(30, ON)  # no nagging while on task
    assert r.brain.line_id == 4


def test_templating():
    ctx = {"app": "Steam", "mode": "Building", "reason": "games", "title": "Hades"}
    assert render_line("{app} in {mode}: {reason} ({title})", ctx) == "Steam in Building: games (Hades)"
    assert render_line("{app} {unknown}", ctx) == "Steam {unknown}"
    assert render_line("broken {", ctx) == "broken {"
    assert render_line("{0}", ctx) == "{0}"
    r = Rig()
    r.brain.on_activity({**OFF, "app": "com.t3tools.T3Code"})
    assert r.brain.ctx["app"] == "T3Code"


def test_mute_keeps_mood_drops_lines_and_growth():
    r = Rig(PetConfig(muted=True))
    r.run(400, OFF)
    snap = r.brain.snapshot()
    assert snap["mood"] == "furious" and snap["muted"] is True
    assert snap["line"] == "" and snap["scale"] == 1.0
    r.brain.set_muted(False)
    r.run(10)
    assert r.brain.scale > 1.0 and r.brain.line


def test_calm_force_and_say():
    r = Rig()
    r.brain.force_mood("furious")
    assert r.brain.mood == "furious" and r.brain.scale == 24.0 and "HISS" in r.brain.line
    r.run(3, ON)
    assert r.brain.scale == 24.0  # a preview holds while forced
    r.brain.force_mood("auto")
    r.run(4)
    assert r.brain.mood == "content" and r.brain.scale == 1.0
    with pytest.raises(ValueError):
        r.brain.force_mood("sleepy")
    r.run(200, OFF)
    r.brain.say("psst")
    assert r.brain.line == "psst"
    r.brain.calm()
    s = r.brain.snapshot()
    assert (s["mood"], s["scale"], s["line"], s["off_seconds"], s["forced"]) == ("content", 1.0, "", 0, None)


def test_snapshot_shape_and_change_spam():
    r = Rig(PetConfig(position="right"))
    s = r.brain.snapshot()
    assert {"name", "mood", "scale", "line", "off_seconds", "pack", "pack_dir", "muted"} <= set(s)
    assert s["name"] == "Miso" and s["pack_dir"] == "/packs/cat" and s["position"] == "right"
    assert s["size"] == 48 and s["max_screen_fraction"] == 0.9
    assert s["config"] == {"thresholds": {"suspicious": 45, "annoyed": 120, "furious": 300}, "grow_s": 240,
                           "shrink_s": 4, "decay_per_s": 2, "nag_every_s": 60, "max_scale": 24}
    json.dumps(s)
    r.run(30, ON)
    assert r.changes == 0  # nothing changed, nothing published
    r.run(3, OFF)
    assert r.changes == 3  # off_seconds (whole seconds) changed each tick


def test_missing_pack_falls_back_to_cat():
    r = Rig(PetConfig(pack="nope"))
    assert r.brain.pack_dir == "/packs/cat"
    assert Rig(packs=FakePetPacks({})).brain.snapshot()["pack_dir"] == ""


def test_llm_speaker_replaces_mood_change_lines():
    sp = FakeSpeaker("you and that video, honestly")
    r = Rig(PetConfig(llm_lines=True), speaker=sp)
    r.run(45, OFF)
    assert r.brain.line.startswith("hmm.")  # template first, instantly
    r.spawner.drain()
    assert r.brain.line == "you and that video, honestly"
    assert sp.calls == [("suspicious", "Writing", "YouTube", "cats compilation", "video")]
    r.run(60)  # nags use templates
    r.spawner.drain()
    assert len(sp.calls) == 1
    r2 = Rig(PetConfig(llm_lines=False), speaker=sp)
    r2.run(45, OFF)
    assert not r2.spawner.coros


def _pack(root: Path, name: str, title: str, valid: bool = True) -> None:
    (root / name).mkdir(parents=True)
    (root / name / "pack.json").write_text(json.dumps({"name": title, "moods": {}}) if valid else "{oops")


def test_pack_resolution(tmp_path):
    user, builtin = tmp_path / "user", tmp_path / "builtin"
    _pack(builtin, "cat", "Built-in cat")
    _pack(builtin, "fox", "Fox")
    _pack(user, "cat", "My cat")
    _pack(user, "broken", "x", valid=False)
    packs = DirPetPacks([("user", user), ("built-in", builtin)])
    assert packs.resolve("cat") == (str(user / "cat"), {"name": "My cat", "moods": {}})
    assert packs.resolve("fox")[0] == str(builtin / "fox")
    assert packs.resolve("broken") is None and packs.resolve("../builtin/cat") is None
    assert packs.resolve("") is None
    assert [(p["name"], p["source"]) for p in packs.available()] == [("cat", "user"), ("fox", "built-in")]
    assert DirPetPacks([("user", tmp_path / "missing")]).available() == []


@pytest.mark.parametrize("pack", ["cat", "icona-cat"])
def test_builtin_packs_are_complete(pack):
    pack_dir, manifest = DirPetPacks([("built-in", BUILTIN_PETS_DIR)]).resolve(pack)
    assert Path(pack_dir).name == pack
    assert set(manifest["moods"]) == set(MOODS) and manifest["size"] == 48
    assert manifest.get("pixel", True) is (pack == "cat")   # icona-cat is vector art, drawn smoothed
    for mood in manifest["moods"].values():
        assert mood["fps"] > 0
        for frame in mood["frames"]:
            assert (Path(pack_dir) / frame).read_text().startswith("<svg")


def test_daemon_activity_listeners(tmp_path):
    spawner = Spawner()
    d = Daemon(config_source=FakeConfigSource(make_config()), classifier=FakeClassifier(), sink=FakeSink(),
               publisher=FakePublisher(), runner=FakeRunner(), clock=FakeClock(), spawn=spawner)
    seen: list[dict] = []
    d.activity_listeners.append(seen.append)
    d.start(WindowInfo("kitty", "zsh"))
    spawner.drain()
    assert seen == [{"verdict": "on", "reason": "everything is on task in Free", "app": "kitty", "title": "zsh",
                     "source": "rule", "mode": "Free"}]


def test_feature_commands(tmp_path, monkeypatch):
    from lockdock.features import pet as feature
    monkeypatch.setattr(feature, "PET_FILE", tmp_path / "pet.json")
    monkeypatch.setattr(feature, "USER_PETS_DIR", tmp_path / "pets")
    _pack(tmp_path / "pets", "blob", "Blob")
    pub = FakePublisher()
    d = Daemon(config_source=FakeConfigSource(make_config()), classifier=FakeClassifier(), sink=FakeSink(),
               publisher=pub, runner=FakeRunner(), clock=FakeClock(), spawn=Spawner())
    tasks = feature.install(d)
    assert len(tasks) == 2
    for t in tasks:
        t.close()
    assert d.snapshot()["pet"]["mood"] == "content"
    assert d.handle("pet", ["mood", "furious"]) == "mood furious (forced)"
    assert pub.snapshots[-1]["pet"]["scale"] == 24.0
    assert d.handle("pet", ["mood", "sleepy"]).startswith("unknown mood")
    assert d.handle("pet", "say hello there") == "said" and d.snapshot()["pet"]["line"] == "hello there"
    assert d.handle("pet", ["calm"]) == "calmed" and d.snapshot()["pet"]["mood"] == "content"
    assert d.handle("pet", ["mute"]) == "muted"
    assert json.loads((tmp_path / "pet.json").read_text())["muted"] is True
    assert d.handle("pet", ["unmute"]) == "unmuted"
    assert d.handle("pet", ["pack", "nope"]).startswith("no pack")
    assert d.handle("pet", ["pack", "blob"]) == "pack blob"
    assert d.snapshot()["pet"]["pack_dir"] == str(tmp_path / "pets" / "blob")
    assert {p["name"] for p in d.handle("pet", ["packs"])} >= {"blob", "cat"}
    assert d.handle("pet", None)["pack"] == "blob"
    assert d.handle("pet", ["dance"]).startswith("usage")
    d.activity_listeners[0](OFF)
    assert d.handle("pet", None)["off_seconds"] == 0


def test_pet_setting_validation():
    cfg = PetConfig()
    assert pet_setting(cfg, "grow_s", 90) == {"grow_s": 90}
    assert pet_setting(cfg, "shrink_s", 0.5) == {"shrink_s": 0.5}
    assert pet_setting(cfg, "thresholds.annoyed", 60.0) == {"thresholds": {"suspicious": 45, "annoyed": 60,
                                                                           "furious": 300}}
    assert pet_setting(cfg, "thresholds.furious", 120)["thresholds"]["furious"] == 120   # equal is fine
    for key, value, msg in (("grow_s", 0.5, "grow_s must be 1 or more"), ("nag_every_s", 4, "5 or more"),
                            ("max_scale", 0, "1 or more"), ("decay_per_s", -1, "0 or more"),
                            ("thresholds.annoyed", 30, "in order"), ("thresholds.furious", 100, "in order"),
                            ("thresholds.suspicious", -5, "0 or more"), ("grow_s", "fast", "a number"),
                            ("grow_s", True, "a number"), ("lines", 1, "unknown pet setting"),
                            ("max_screen_fraction", 0.5, "unknown pet setting")):
        with pytest.raises(ValueError, match=msg):
            pet_setting(cfg, key, value)


def test_set_timing_applies_live_and_publishes():
    r = Rig()
    before = r.changes
    r.brain.apply_config(pet_config_from_dict(pet_setting(r.brain.cfg, "thresholds.suspicious", 10)))
    assert r.changes == before + 1 and r.brain.snapshot()["config"]["thresholds"]["suspicious"] == 10
    r.run(10, OFF)
    assert r.brain.mood == "suspicious"


def test_feature_pet_set(tmp_path, monkeypatch):
    from lockdock.features import pet as feature
    monkeypatch.setattr(feature, "PET_FILE", tmp_path / "pet.json")
    pub = FakePublisher()
    d = Daemon(config_source=FakeConfigSource(make_config()), classifier=FakeClassifier(), sink=FakeSink(),
               publisher=pub, runner=FakeRunner(), clock=FakeClock(), spawn=Spawner())
    for t in feature.install(d):
        t.close()
    assert d.handle("pet", ["set", "grow_s", "90"]) == "grow_s = 90"
    assert d.handle("pet", "set thresholds.furious 600") == "thresholds.furious = 600"
    raw = json.loads((tmp_path / "pet.json").read_text())
    assert raw["grow_s"] == 90 and raw["thresholds"] == {"suspicious": 45, "annoyed": 120, "furious": 600}
    assert pub.snapshots[-1]["pet"]["config"]["grow_s"] == 90
    assert d.handle("pet", ["set", "grow_s", "0"]) == "grow_s must be 1 or more"
    assert d.handle("pet", ["set", "grow_s", "x"]).startswith("Expecting value")
    assert d.handle("pet", ["set", "grow_s"]).startswith("usage: pet set")
    assert json.loads((tmp_path / "pet.json").read_text())["grow_s"] == 90
