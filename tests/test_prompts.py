import asyncio
from dataclasses import replace

from lockdock.adapters import claude_cli
from lockdock.adapters.json_config import config_from_dict
from lockdock.core.daemon import Daemon
from lockdock.core.models import Mode, Notification, NotificationRules, NotificationVerdict, WindowInfo
from lockdock.core.prompts import PromptCenter, belongs_to, held_for, host_of
from lockdock.features import prompts as prompts_feature

from .fakes import (FakeClassifier, FakeClock, FakeConfigSource, FakeEvents, FakePublisher, FakeRunner, FakeSink,
                    Spawner, make_config)

PROMPT_KEYS = {"id", "kind", "created_ms", "expires_ms", "icon", "title", "subtitle", "body", "tag", "actions"}


def social_config(**kw):
    cfg = make_config(**kw)
    social = Mode(id="social", label="Social", on_task=[r"x\.com|/ X -", "reddit", "instagram"],
                  notifications=NotificationRules(allow_from=["Slack"], default="pass"))
    cfg.modes.append(social)
    return cfg


class Harness:
    def __init__(self, mode="writing", cfg=None, clf=None):
        self.cfg = cfg or social_config()
        self.mode = mode
        self.clock, self.events, self.spawner = FakeClock(), FakeEvents(), Spawner()
        self.changes: list[int] = []
        self.requests: list[str] = []
        self.clf = clf or FakeClassifier()
        self.c = PromptCenter(lambda: self.cfg, lambda: self.cfg.get(self.mode), self._request, self.clf,
                              self.clock, self.events, lambda: self.changes.append(1), self.spawner)

    def _request(self, mode_id: str) -> str:
        self.requests.append(mode_id)
        return f"requested {mode_id}"


def x_activity(verdict="off", source="rule", url="https://x.com/home", reason="matches off_task rule"):
    return {"verdict": verdict, "reason": reason, "app": "helium", "title": "Home / X", "url": url,
            "source": source, "mode": "Writing"}


def slack(summary="Maya Chen", body="can you sign off on the launch post?", app="Slack"):
    return Notification(app=app, summary=summary, body=body, desktop_entry=app.lower())


# ---------- resolution ----------
def test_host_of():
    assert host_of("https://www.x.com/home") == "x.com"
    assert host_of("tidepool.dev/docs") == "tidepool.dev"
    assert host_of(None) == "" and host_of("") == ""


def test_belongs_to_resolution():
    cfg = social_config()
    w = cfg.get("writing")
    assert belongs_to(cfg, w, WindowInfo("helium", "Home / X", "https://x.com/home")).id == "social"
    assert belongs_to(cfg, w, WindowInfo("helium", "github.com/foo")).id == "building"   # on_task rule
    assert belongs_to(cfg, w, WindowInfo("kitty", "zsh")).id == "building"             # mode app
    assert belongs_to(cfg, w, WindowInfo("helium", "random page")) is None             # browser is no mode app
    assert belongs_to(cfg, w, WindowInfo("helium", "cats - YouTube")) is None          # free is a catch-all
    # a mode whose off_task matches the window does not claim it
    cfg.get("social").off_task = ["x\\.com"]
    assert belongs_to(cfg, w, WindowInfo("helium", "Home / X", "https://x.com/home")) is None
    # the current mode is skipped
    assert belongs_to(cfg, cfg.get("social"), WindowInfo("helium", "reddit")) is None


def test_held_for():
    cfg = social_config()
    w = cfg.get("writing")
    assert held_for(cfg, w, slack()).id == "social"
    assert held_for(cfg, w, slack(app="Mail")) is None
    assert held_for(cfg, w, slack(app="kitty")).id == "building"   # apps match too


# ---------- site cards ----------
def test_site_card_schema():
    h = Harness()
    h.c.on_activity(x_activity())
    (p,) = h.c.snapshot()
    assert set(p) == PROMPT_KEYS
    assert p == {"id": "p1", "kind": "site", "created_ms": 1000000, "expires_ms": None, "icon": "helium",
                 "title": "x.com", "subtitle": "belongs to Social", "body": "Stay focused, or switch?",
                 "tag": None,
                 "actions": [{"id": "stay", "label": "Stay", "style": "plain"},
                             {"id": "switch", "label": "Go to Social (30s wait)", "style": "primary",
                              "mode": "social"}]}
    assert h.events.records[-1]["kind"] == "prompt" and h.events.records[-1]["op"] == "open"


def test_site_card_without_wait_and_by_class():
    cfg = social_config()
    cfg.get("writing").exit_delay_s = 0
    h = Harness(cfg=cfg)
    h.c.on_activity({"verdict": "off", "reason": "r", "app": "kitty", "title": "zsh", "source": "rule"})
    (p,) = h.c.snapshot()
    assert p["title"] == "kitty" and p["actions"][1]["label"] == "Go to Building"


def test_newer_site_card_replaces_one_from_the_same_window_class():
    h = Harness()
    h.c.on_activity(x_activity(url=None))       # judged by title before the URL arrived
    h.c.on_activity(x_activity())
    assert [p["title"] for p in h.c.snapshot()] == ["x.com"]


def test_on_task_or_neutral_opens_no_site_card():
    h = Harness()
    h.c.on_activity(x_activity(verdict="on"))
    h.c.on_activity(x_activity(verdict="neutral"))
    assert h.c.snapshot() == []


def test_site_snooze_and_stay():
    h = Harness()
    h.c.on_activity(x_activity())
    h.c.on_activity(x_activity())                       # open already
    assert len(h.c.prompts) == 1
    assert h.c.act("p1", "stay").startswith("staying")
    h.clock.t += 300
    h.c.on_activity(x_activity())                       # snoozed
    assert h.c.prompts == []
    h.clock.t += 301
    h.c.on_activity(x_activity())
    assert len(h.c.prompts) == 1


def test_site_once_per_snooze_even_after_later():
    h = Harness()
    h.c.on_activity(x_activity())
    h.c.act("p1", "later")
    h.c.on_activity(x_activity())
    assert h.c.prompts == []


def test_mode_switch_resets_snooze_and_clears():
    h = Harness()
    h.c.on_activity(x_activity())
    h.c.act("p1", "stay")
    h.c.on_held(slack(), None)
    h.spawner.discard()
    h.c.on_switch(h.cfg.get("writing"), h.cfg.get("building"))
    assert h.c.prompts == []
    h.c.on_switch(h.cfg.get("building"), h.cfg.get("writing"))
    h.c.on_activity(x_activity())
    assert len(h.c.prompts) == 1


def test_disabled_flags():
    cfg = social_config()
    cfg.prompts = replace(cfg.prompts, site_cards=False)
    h = Harness(cfg=cfg)
    h.c.on_activity(x_activity())
    assert h.c.prompts == []
    cfg.prompts = replace(cfg.prompts, enabled=False, site_cards=True)
    h.c.on_activity(x_activity())
    h.c.on_held(slack(), None)
    assert h.c.prompts == []


# ---------- verdict toasts ----------
def test_verdict_toast_from_live_llm_only():
    h = Harness(mode="building")
    tide = {"verdict": "on", "reason": "API docs for an incident tool", "app": "helium",
            "title": "Tidepool", "url": "https://tidepool.dev/api", "source": "llm"}
    h.c.on_activity({**tide, "source": "cache"})
    h.c.on_activity({**tide, "source": "rule"})
    assert h.c.prompts == []
    h.c.on_activity(tide)
    (p,) = h.c.snapshot()
    assert p["kind"] == "verdict" and p["actions"] == [] and p["expires_ms"] == 1006000
    assert p["title"] == "tidepool.dev" and p["subtitle"] == "not in any mode"
    assert p["tag"] == {"label": "Fits Building", "detail": "API docs for an incident tool", "level": "ok"}
    h.c.on_activity({**tide, "verdict": "off", "reason": "shopping"})   # replaces the toast for that host
    (p,) = h.c.snapshot()
    assert p["tag"] == {"label": "Off task", "detail": "shopping", "level": "urgent"}


def test_llm_verdict_on_a_site_another_mode_owns_is_no_toast():
    h = Harness(mode="building")
    h.c.on_activity(x_activity(verdict="on", source="llm"))
    assert h.c.prompts == []


def test_expiry_on_tick():
    h = Harness(mode="building")
    h.c.on_activity({"verdict": "on", "reason": "r", "app": "helium", "title": "t",
                     "url": "https://tidepool.dev", "source": "llm"})
    h.clock.t += 5
    h.c.tick()
    assert len(h.c.prompts) == 1
    h.clock.t += 1
    h.c.tick()
    assert h.c.prompts == [] and h.events.records[-1]["op"] == "expire"


# ---------- notification cards ----------
def test_notification_card_with_switch():
    h = Harness(clf=FakeClassifier(notification=NotificationVerdict("hold", "lunch", False)))
    h.c.on_held(slack(body="x" * 300), None)
    (p,) = h.c.snapshot()
    assert set(p) == PROMPT_KEYS
    assert p["kind"] == "notification" and p["icon"] == "slack" and p["title"] == "Maya Chen"
    assert p["subtitle"] == "Slack · held for Social" and len(p["body"]) == 160 and p["expires_ms"] is None
    assert p["actions"] == [{"id": "later", "label": "Later", "style": "plain"},
                            {"id": "switch", "label": "Go to Social (30s wait)", "style": "primary",
                             "mode": "social"}]
    h.spawner.drain()
    assert h.c.snapshot()[0]["tag"] is None and len(h.clf.calls) == 1


def test_notification_card_without_switch():
    h = Harness(cfg=social_config(llm_enabled=False))
    h.c.on_held(slack(app="Mail"), None)
    (p,) = h.c.snapshot()
    assert p["subtitle"] == "Mail · held in Writing"
    assert [a["id"] for a in p["actions"]] == ["later"]


def test_tag_from_given_verdict_and_no_extra_call():
    h = Harness()
    h.c.on_held(slack(), NotificationVerdict("hold", "Maya is waiting", True, "3pm"))
    assert h.c.snapshot()[0]["tag"] == {"label": "Time-sensitive", "detail": "needs your answer before 3pm",
                                        "level": "urgent"}
    assert h.spawner.coros == []


def test_tag_fetched_for_rule_held():
    h = Harness(clf=FakeClassifier(notification=NotificationVerdict("hold", "someone is waiting", True)))
    h.c.on_held(slack(), None)
    assert h.c.snapshot()[0]["tag"] is None
    h.spawner.drain()
    assert h.c.snapshot()[0]["tag"] == {"label": "Time-sensitive", "detail": "someone is waiting",
                                        "level": "urgent"}


def test_no_tag_call_when_llm_disabled():
    h = Harness(cfg=social_config(llm_enabled=False))
    h.c.on_held(slack(), None)
    assert h.spawner.coros == [] and h.c.snapshot()[0]["tag"] is None


def test_cap_of_three_drops_oldest():
    h = Harness(cfg=social_config(llm_enabled=False))
    for i in range(4):
        h.c.on_held(slack(summary=f"m{i}"), None)
    assert [p["title"] for p in h.c.snapshot()] == ["m1", "m2", "m3"]


# ---------- actions ----------
def test_actions():
    h = Harness(cfg=social_config(llm_enabled=False))
    h.c.on_held(slack(), None)
    h.c.on_held(slack(app="Mail"), None)
    assert h.c.act("p9", "later") == "no open prompt 'p9'"
    assert h.c.act("p2", "switch").startswith("prompt p2 has no action")
    assert h.c.act("p2", "later") == "dismissed"
    assert h.c.handle_act({"id": "p1", "action": "switch"}) == "requested social"
    assert h.requests == ["social"] and h.c.prompts == []
    acts = [r for r in h.events.records if r.get("op") == "act"]
    assert [(r["id"], r["action"]) for r in acts] == [("p2", "later"), ("p1", "switch")]


# ---------- daemon wiring ----------
def make_daemon(tmp_path, cfg=None):
    pub, spawner = FakePublisher(), Spawner()
    d = Daemon(config_source=FakeConfigSource(cfg or social_config(llm_enabled=False)), classifier=FakeClassifier(),
               sink=FakeSink(), publisher=pub, runner=FakeRunner(), clock=FakeClock(),
               events_path=tmp_path / "events.jsonl", spawn=spawner)
    for coro in prompts_feature.install(d):
        coro.close()
    return d, pub, spawner


def test_daemon_switch_presses_the_countdown(tmp_path):
    d, pub, spawner = make_daemon(tmp_path)
    d.modes.activate("writing")
    d.gate.on_notify(slack())
    st = pub.snapshots[-1]
    assert st["prompts_count"] == 1 and st["prompts"][0]["subtitle"] == "Slack · held for Social"
    assert d.handle("prompt_act", {"id": "p1", "action": "switch"}).startswith("leaving Writing in 30s")
    assert d.modes.pending.mode == "social" and d.modes.pending.deadline == 1030.0
    d.gate.on_notify(slack(summary="again"))
    d.handle("prompt_act", {"id": "p2", "action": "switch"})
    assert d.modes.pending.deadline == 1020.0            # a second press cut per_press_s
    assert d.handle("prompts", None) == []
    spawner.discard()
    assert '"kind": "prompt"' in (tmp_path / "events.jsonl").read_text()


def test_daemon_site_card_via_judge(tmp_path):
    d, pub, spawner = make_daemon(tmp_path)
    d.cfg.get("writing").off_task.append(r"x\.com")
    d.modes.activate("writing")
    spawner.discard()
    d.judge.focus = WindowInfo("helium", "Home / X", "https://x.com/home")
    asyncio.run(d.judge.judge())
    st = pub.snapshots[-1]
    assert st["activity"]["source"] == "rule"
    assert st["prompts"][0]["title"] == "x.com" and st["prompts"][0]["subtitle"] == "belongs to Social"
    d.modes.activate("social")
    assert pub.snapshots[-1]["prompts"] == []


# ---------- config and adapter ----------
def test_config_prompts_block():
    base = {"modes": [{"id": "a"}]}
    assert config_from_dict(base).prompts.stay_snooze_s == 600
    cfg = config_from_dict({**base, "prompts": {"verdict_toasts": False, "stay_snooze_s": 60}})
    assert cfg.prompts.verdict_toasts is False and cfg.prompts.stay_snooze_s == 60 and cfg.prompts.site_cards


def test_claude_notification_verdict(tmp_path, monkeypatch):
    calls = []

    async def fake_ask(system, user, model, timeout_s):
        calls.append(user)
        return {"action": "hold", "reason": "Maya waits", "time_sensitive": True, "deadline": "3pm"}

    monkeypatch.setattr(claude_cli, "ask_claude", fake_ask)
    clf = claude_cli.ClaudeCliClassifier(claude_cli.JsonFileCache(tmp_path / "c.json"))
    mode = social_config().get("writing")
    v = asyncio.run(clf.notification(mode, slack()))
    assert v == NotificationVerdict("hold", "Maya waits", True, "3pm")
    v2 = asyncio.run(clf.notification(mode, slack(body="other body")))
    assert v2.cached and v2.time_sensitive and v2.deadline == "3pm" and len(calls) == 1
