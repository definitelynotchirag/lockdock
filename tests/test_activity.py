import asyncio

from lockdock.core.activity import ActivityJudge, rule_activity
from lockdock.core.models import ActivityVerdict, Verdict, WindowInfo
from lockdock.core.rules import matches, norm_title

from .fakes import FakeClassifier, FakeClock, FakeEvents, Spawner, make_config

CFG = make_config()
WRITING = CFG.get("writing")
BUILDING = CFG.get("building")
BROWSERS = CFG.browsers


def test_rules_helpers():
    assert matches(["you(tube"], "YOU(TUBE video") == "you(tube"  # bad regex -> substring
    assert matches([r"docs\.google"], "helium|Docs.Google.com") == r"docs\.google"
    assert matches(["x"], "abc") is None
    assert norm_title("(3) Inbox  42 New") == "inbox # new"


def test_off_beats_on():
    v, why = rule_activity(WRITING, WindowInfo("helium", "obsidian tips - YouTube"), BROWSERS)
    assert v == Verdict.OFF and "youtube" in why


def test_on_task_rule():
    assert rule_activity(WRITING, WindowInfo("helium", "Wikipedia"), BROWSERS)[0] == Verdict.ON


def test_mode_app_is_on():
    assert rule_activity(BUILDING, WindowInfo("kitty", "zsh"), BROWSERS) == (Verdict.ON, "mode app")


def test_browser_is_never_on_by_being_a_mode_app():
    # helium is a writing app, but browsers are judged by title only -> unknown -> ask
    assert rule_activity(WRITING, WindowInfo("helium", "Some random page"), BROWSERS) is None


def test_unknown_policies():
    free = CFG.get("free")
    assert rule_activity(free, WindowInfo("steam", "x"), BROWSERS)[0] == Verdict.ON  # .* on_task
    free.on_task = []
    assert rule_activity(free, WindowInfo("steam", "x"), BROWSERS)[0] == Verdict.NEUTRAL
    free.unknown = "off"
    assert rule_activity(free, WindowInfo("steam", "x"), BROWSERS)[0] == Verdict.OFF


def make_judge(mode: str, classifier: FakeClassifier | None = None, **cfg_kw):
    cfg = make_config(**cfg_kw)
    events, changes, nudges, spawner = FakeEvents(), [], [], Spawner()
    j = ActivityJudge(lambda: cfg, lambda: cfg.get(mode), classifier or FakeClassifier(), FakeClock(), events,
                      lambda: changes.append(dict(j.activity)), lambda m, w, r: nudges.append(r), spawner)
    return j, events, changes, nudges, spawner


def test_judge_no_window():
    j, *_ = make_judge("writing")
    asyncio.run(j.judge())
    assert j.activity["reason"] == "no window"


def test_judge_falls_back_to_classifier():
    clf = FakeClassifier(activity=(Verdict.OFF, "shopping"))
    j, events, changes, nudges, _ = make_judge("writing", clf)
    j.focus = WindowInfo("helium", "Amazon")
    asyncio.run(j.judge())
    assert changes[0]["reason"] == "classifying…"
    assert j.activity == {"verdict": "off", "reason": "shopping", "app": "helium", "title": "Amazon",
                          "source": "llm"}
    assert events.records[-1]["verdict"] == "off"
    assert nudges == []  # off_task_action defaults to nudge, not notify


def test_judge_notify_action_fires_once():
    j, _, _, nudges, _ = make_judge("writing")
    j._mode().off_task_action = "notify"
    j.focus = WindowInfo("helium", "cats - YouTube")
    asyncio.run(j.judge())
    asyncio.run(j.judge())
    assert nudges == ["matches off_task rule 'youtube'"]


def test_judge_llm_disabled():
    clf = FakeClassifier()
    j, *_ = make_judge("writing", clf, llm_enabled=False)
    j.focus = WindowInfo("steam", "x")
    asyncio.run(j.judge())
    assert j.activity["reason"] == "unknown app, llm disabled" and clf.calls == []


def test_judge_drops_stale_verdict():
    j, events, *_ = make_judge("writing")

    class Moving(FakeClassifier):
        async def activity(self, mode, window):
            j.focus = WindowInfo("kitty", "elsewhere")
            return ActivityVerdict(Verdict.OFF, "late")

    j.classifier = Moving()
    j.focus = WindowInfo("helium", "Amazon")
    asyncio.run(j.judge())
    assert j.activity["reason"] == "classifying…" and events.records == []


def test_on_focus_schedules_dwell():
    j, _, _, _, spawner = make_judge("building")
    j.on_focus(WindowInfo("dev.zed.Zed", "main.py"))
    spawner.drain()
    assert j.activity["verdict"] == "on"
