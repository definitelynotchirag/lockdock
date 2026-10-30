import asyncio

from lockdock.core.models import Notification
from lockdock.core.notifications import NotificationGate, decide, release_messages

from .fakes import FakeClassifier, FakeClock, FakeEvents, FakeSink, Spawner, make_config

CFG = make_config()


def n(app="Slack", summary="hi", body="", urgency=1, entry="", cookie=1, sender=":1.5"):
    return Notification(app=app, summary=summary, body=body, urgency=urgency, desktop_entry=entry,
                        cookie=cookie, sender=sender)


def test_decide_rules():
    w = CFG.get("writing")
    assert decide(w, n(urgency=2, app="Discord")).action == "pass"
    assert decide(w, n(app="Discord", summary="urgent")).reason == "hold_from 'Discord'"
    assert decide(w, n(app="Calendar")).action == "pass"
    assert decide(w, n(summary="URGENT: prod")).reason == "keyword 'urgent'"
    assert decide(w, n()).reason == "mode default 'hold'"
    assert decide(CFG.get("free"), n()).action == "pass"
    assert decide(CFG.get("building"), n()).action == "ask"


def make_gate(mode="writing", clf=None, clock=None, limit_s=0.0):
    sink, events, changes, spawner = FakeSink(), FakeEvents(), [], Spawner()
    g = NotificationGate(lambda: CFG.get(mode), clf or FakeClassifier(), sink, events,
                         lambda: changes.append(1), clock or FakeClock(), spawner, lambda: limit_s)
    return g, sink, events, changes, spawner


def test_hold_then_close_on_reply():
    g, sink, events, changes, _ = make_gate()
    g.on_notify(n(cookie=7))
    assert len(g.held) == 1 and changes == [1]
    g.on_reply(7, 42, ":1.5")
    assert sink.closed == [42] and g.held[0].id == 42
    g.on_reply(7, 42, ":1.5")
    assert sink.closed == [42]


def test_pass_is_untouched():
    g, sink, *_ = make_gate()
    g.on_notify(n(app="Calendar", cookie=3))
    g.on_reply(3, 5, ":1.5")
    assert g.held == [] and sink.closed == []


def test_ask_pass_resends():
    g, sink, events, _, spawner = make_gate("building", FakeClassifier(notification=("pass", "ok")))
    g.on_notify(n(cookie=9))
    g.on_reply(9, 11, ":1.5")
    assert sink.closed == [11]
    spawner.drain()
    assert sink.sent[0]["app"] == "Slack" and g.held == []
    assert events.records[-1]["action"] == "pass"


def test_ask_hold_holds():
    g, sink, _, _, spawner = make_gate("building", FakeClassifier(notification=("hold", "later")))
    g.on_notify(n())
    spawner.drain()
    assert len(g.held) == 1 and sink.sent == []


def test_release_individual_and_summary():
    few = [n(app=f"a{i}") for i in range(5)]
    msgs = release_messages(few, "while you were in Writing")
    assert len(msgs) == 5 and msgs[0].body.endswith("(while you were in Writing)")
    many = [n(app="Slack")] * 4 + [n(app="Mail")] * 2
    (m,) = release_messages(many, "on request")
    assert m.app == "lockdock" and m.summary == "6 notifications held on request"
    assert m.body == "Slack ×4, Mail ×2"


def test_gate_release():
    g, sink, events, _, _ = make_gate()
    assert g.release("x") == 0
    g.on_notify(n())
    g.on_notify(n(app="Mail"))
    assert g.release("on request") == 2
    assert g.held == [] and len(sink.sent) == 2 and events.kinds()[-1] == "release"


def test_expire_after_the_time_limit():
    clock = FakeClock()
    g, sink, events, changes, _ = make_gate(clock=clock, limit_s=15 * 60)
    released = []
    g.release_listeners.append(released.append)
    g.on_notify(n(summary="old", body="b"))
    clock.t += 5 * 60
    g.on_notify(n(app="Mail", summary="new"))
    assert g.expire(clock.now()) == 0
    clock.t += 10 * 60
    before = len(changes)
    assert g.expire(clock.now()) == 1
    assert sink.sent == [{"app": "Slack", "summary": "old", "body": "b\n(held 15 min in Writing)",
                          "desktop_entry": "", "urgency": 1, "timeout_ms": -1}]
    assert [x.summary for x in g.held] == ["new"] and len(changes) == before + 1
    assert [x.summary for x in released[0]] == ["old"]
    assert events.records[-1] == {"kind": "release", "count": 1, "reason": "time limit"}


def test_expire_never_when_the_limit_is_zero():
    clock = FakeClock()
    g, sink, *_ = make_gate(clock=clock, limit_s=0)
    g.on_notify(n())
    clock.t += 10 ** 6
    assert g.expire(clock.now()) == 0 and len(g.held) == 1 and sink.sent == []


def test_dnd_holds_everything_silently_and_releases_on_off():
    clock = FakeClock()
    g, sink, events, _, _ = make_gate(mode="free", clock=clock)
    heard = []
    g.hold_listeners.append(lambda note, v: heard.append(note))
    g.on_notify(n(app="Discord", summary="before"))      # free passes everything
    assert g.held == []
    g.set_dnd(True)
    g.on_notify(n(summary="a", cookie=1))
    g.on_notify(n(summary="crit", urgency=2, cookie=2))   # even critical
    g.on_reply(1, 50, ":1.5")
    assert [x.summary for x in g.held] == ["a", "crit"] and sink.closed == [50] and heard == []
    assert {"kind": "notification", "app": "Slack", "summary": "a", "action": "hold",
            "reason": "do not disturb"} in events.records
    assert g.set_dnd(False) == 2
    assert g.held == [] and sink.sent[0]["body"] == "\n(while you were in do not disturb)"
    assert events.records[-1] == {"kind": "dnd", "on": False, "released": 2}
    assert g.set_dnd(False) == 0


def test_dnd_off_keeps_what_the_mode_held():
    g, sink, *_ = make_gate()
    g.on_notify(n(summary="mode"))
    g.set_dnd(True)
    g.on_notify(n(summary="dnd"))
    assert g.set_dnd(False) == 1 and [x.summary for x in g.held] == ["mode"]


def test_dnd_holds_an_ask_that_passes():
    g, sink, _, _, spawner = make_gate("building", FakeClassifier(notification=("pass", "ok")))
    g.on_notify(n())
    g.set_dnd(True)
    spawner.drain()
    assert sink.sent == [] and len(g.held) == 1


def test_dnd_hold_expires_with_its_label():
    clock = FakeClock()
    g, sink, *_ = make_gate(clock=clock, limit_s=60)
    g.set_dnd(True)
    g.on_notify(n(body="x"))
    clock.t += 120
    assert g.expire(clock.now()) == 1 and sink.sent[0]["body"] == "x\n(held 2 min in do not disturb)"
