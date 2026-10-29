from lockdock.core.modes import ModeManager

from .fakes import FakeClock, FakeEvents, FakeRunner, Spawner, make_config


def make(mode: str = "writing"):
    cfg = make_config()
    clock, runner, events, spawner = FakeClock(), FakeRunner(), FakeEvents(), Spawner()
    switches: list[tuple[str, str]] = []
    changes: list[int] = []
    mm = ModeManager(lambda: cfg, clock, runner, events, lambda o, n: switches.append((o.id, n.id)),
                     lambda: changes.append(1), spawner)
    mm.mode = mode
    return mm, clock, runner, events, spawner, switches, changes


def test_unknown_and_same_mode():
    mm, *_ = make()
    assert mm.request("nope") == "unknown mode 'nope'"
    assert mm.request("writing") == "already in writing"


def test_no_delay_switches_immediately_and_runs_commands():
    mm, _, runner, events, _, switches, _ = make("free")
    assert mm.request("writing") == "switched to writing"
    assert mm.mode == "writing"
    assert runner.cmds == ["echo enter-writing"]
    assert switches == [("free", "writing")]
    assert "switch" in events.kinds()


def test_countdown_and_press_math():
    mm, clock, runner, events, spawner, switches, _ = make("writing")
    assert mm.request("building") == "leaving Writing in 30s (press again to cut 10s)"
    assert mm.pending and mm.pending.deadline == clock.t + 30 and mm.pending.total == 30
    assert len(spawner.coros) == 1
    assert mm.request("building") == "20s left"
    clock.t += 5
    assert mm.request("building") == "5s left"
    assert mm.request("building") == "switched to building"
    assert mm.mode == "building" and mm.pending is None
    assert runner.cmds == ["echo exit-writing", "echo enter-building"]
    assert switches == [("writing", "building")]
    assert [r["remaining"] for r in events.records if r["kind"] == "press"] == [20.0, 5.0, 0.0]
    spawner.discard()


def test_per_press_defaults_to_5():
    mm, _, _, _, spawner, _, _ = make("building")
    assert mm.request("writing").startswith("leaving Building in 20s")
    assert mm.request("writing") == "15s left"
    spawner.discard()


def test_press_on_current_mode_cancels():
    mm, _, _, events, spawner, _, _ = make("writing")
    mm.request("building")
    assert mm.request("writing") == "cancelled pending switch"
    assert mm.pending is None and events.kinds()[-1] == "cancel"
    spawner.discard()


def test_poll_activates_after_deadline():
    mm, clock, _, _, spawner, switches, _ = make("writing")
    mm.request("building")
    mm.poll()
    assert mm.mode == "writing"
    clock.t += 31
    mm.poll()
    assert mm.mode == "building" and switches == [("writing", "building")]
    spawner.discard()


def test_countdown_task_runs_until_switch():
    mm, clock, _, _, spawner, _, _ = make("writing")
    mm.request("building")
    clock.t += 100
    spawner.drain()
    assert mm.mode == "building"


def test_config_changed_falls_back_to_default():
    mm, *_ = make("writing")
    cfg = make_config()
    cfg.modes = [m for m in cfg.modes if m.id != "writing"]
    mm._config = lambda: cfg
    mm.config_changed()
    assert mm.mode == "free"
