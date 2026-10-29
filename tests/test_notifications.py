import asyncio

from lockdock.core.models import Notification
from lockdock.core.notifications import NotificationGate, decide, release_messages

from .fakes import FakeClassifier, FakeEvents, FakeSink, Spawner, make_config

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


def make_gate(mode="writing", clf=None):
    sink, events, changes, spawner = FakeSink(), FakeEvents(), [], Spawner()
    g = NotificationGate(lambda: CFG.get(mode), clf or FakeClassifier(), sink, events,
                         lambda: changes.append(1), spawner)
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
