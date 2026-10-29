import asyncio
import io
import json
import socket
import urllib.error

import pytest

from lockdock.adapters.claude_cli import ClaudeCliClassifier, JsonFileCache
from lockdock.adapters.env_file import load_env_file, lookup
from lockdock.adapters.jev import JevClassifier, readable_rules
from lockdock.app import pick_classifier, sync_classifier
from lockdock.core.models import Notification, Verdict, WindowInfo
from lockdock.features.classify import classify

from .fakes import make_config

KEY = "sk-test-secret"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeUrlopen:
    """Replays queued results (a dict = 200 JSON body, an exception = raised) and records requests."""

    def __init__(self, *results):
        self.results = list(results)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append({"url": req.full_url, "headers": dict(req.header_items()),
                              "body": json.loads(req.data), "timeout": timeout})
        r = self.results.pop(0)
        if isinstance(r, BaseException):
            raise r
        return FakeResponse(json.dumps(r).encode())


def choice(name, c, conf, usage=391):
    return {"model": "jev-1.14.0", "answers": {name: {"type": "choice", "choice": c, "confidence": conf,
                                                      "probabilities": {c: conf}}},
            "usage": {"input_tokens": usage, "output_tokens": 55}}


def http_error(code, detail="boom"):
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(json.dumps({"detail": detail}).encode()))


def jev(tmp_path, opener, **kw):
    usage = []
    c = JevClassifier(JsonFileCache(tmp_path / "cache.json"), KEY, urlopen=opener, on_usage=usage.append, **kw)
    return c, usage


def run(coro):
    return asyncio.run(coro)


WRITING = make_config().get("writing")
BUILDING = make_config().get("building")


def test_activity_request_shape(tmp_path):
    op = FakeUrlopen(choice("fit", "off", 0.9))
    c, _ = jev(tmp_path, op)
    writing = make_config().get("writing")
    writing.description = "Long-form writing in Obsidian."
    run(c.activity(writing, WindowInfo("helium", "Home / X - Helium", "https://x.com/home")))
    req = op.requests[0]
    assert req["url"] == "https://api.typesafe.ai/v1/systemone" and req["timeout"] == 5.0
    assert req["headers"]["Authorization"] == f"Bearer {KEY}"
    body = req["body"]
    assert body["model"] == "jev-latest"
    mode = body["state"]["focus_mode"]
    assert mode["description"] == "Long-form writing in Obsidian." and mode["apps"] == writing.apps
    assert "docs.google" in mode["on_task_examples"] and "youtube" in mode["off_task_examples"]
    assert body["state"]["window"] == {"app_class": "helium", "title": "Home / X - Helium",
                                       "url": "https://x.com/home"}
    q = body["questions"]["fit"]
    assert q["type"] == "choice" and set(q["criteria"]) == {"on", "off", "neutral"}
    assert "Long-form writing in Obsidian." in q["criteria"]["on"] and "wikipedia" in q["criteria"]["on"]
    assert "reddit" in q["criteria"]["off"] and "Writing" in q["instructions"]


def test_readable_rules():
    assert readable_rules(["twitter|x\\.com|/ X -", "docs\\.google"]) == "twitter, x.com, / X -, docs.google"
    assert readable_rules([".*"]) == "anything" and readable_rules([]) == "none listed"


def test_activity_verdict_reason_cache_and_usage(tmp_path):
    op = FakeUrlopen(choice("fit", "off", 0.71))
    c, usage = jev(tmp_path, op)
    w = WindowInfo("helium", "Reddit - Helium")
    v = run(c.activity(WRITING, w))
    assert v.verdict == Verdict.OFF and v.reason == "off p=0.71 · jev" and not v.cached
    assert usage[0]["provider"] == "jev" and usage[0]["input_tokens"] == 391 and "ms" in usage[0]
    assert KEY not in json.dumps(usage)
    again = run(c.activity(WRITING, w))   # served from the cache: no second request
    assert again.cached and again.verdict == Verdict.OFF and len(op.requests) == 1
    assert KEY not in (tmp_path / "cache.json").read_text()


def test_shares_cache_keys_with_claude(tmp_path):
    cache = JsonFileCache(tmp_path / "cache.json")
    w = WindowInfo("helium", "Some page")
    cache.put(f"a|writing|helium|{'some page'}", {"verdict": "on", "reason": "from claude"})
    c = JevClassifier(cache, KEY, urlopen=FakeUrlopen())
    v = run(c.activity(WRITING, w))
    assert v.cached and v.verdict == Verdict.ON and v.reason == "from claude (cached)"


def test_low_confidence_is_neutral(tmp_path):
    c, _ = jev(tmp_path, FakeUrlopen(choice("fit", "off", 0.18)))
    v = run(c.activity(WRITING, WindowInfo("helium", "x")))
    assert v.verdict == Verdict.NEUTRAL and v.reason.startswith("low confidence (p=0.18 off)")
    c2, _ = jev(tmp_path / "..", FakeUrlopen(choice("fit", "off", 0.18)), min_confidence=0.1)
    assert run(c2.activity(BUILDING, WindowInfo("helium", "y"))).verdict == Verdict.OFF


def test_http_error_fails_open_without_caching(tmp_path):
    op = FakeUrlopen(http_error(422, "bad question"))
    c, usage = jev(tmp_path, op)
    v = run(c.activity(WRITING, WindowInfo("helium", "x")))
    assert v.verdict == Verdict.NEUTRAL and v.reason == "jev unavailable: http 422 bad question"
    assert len(op.requests) == 1 and usage[0]["error"].startswith("http 422")   # 4xx: no retry
    assert not (tmp_path / "cache.json").exists()
    op.results.append(http_error(401))
    n = run(c.notification(WRITING, Notification("Slack", "s", "b")))
    assert n.action == "pass" and n.reason == "jev unavailable: http 401 boom (fail open)"


def test_retries_once_on_5xx_and_timeout(tmp_path):
    op = FakeUrlopen(http_error(503), choice("fit", "on", 0.9))
    c, _ = jev(tmp_path, op)
    assert run(c.activity(WRITING, WindowInfo("helium", "a"))).verdict == Verdict.ON and len(op.requests) == 2
    op2 = FakeUrlopen(socket.timeout("t"), urllib.error.URLError(TimeoutError("t")), choice("fit", "on", 0.9))
    c2, _ = jev(tmp_path, op2)
    v = run(c2.activity(WRITING, WindowInfo("helium", "b")))
    assert v.reason == "jev unavailable: timeout" and len(op2.requests) == 2


def test_unexpected_exception_never_escapes(tmp_path):
    c, usage = jev(tmp_path, FakeUrlopen(RuntimeError("weird")))
    assert run(c.activity(WRITING, WindowInfo("helium", "a"))).reason == "jev unavailable: RuntimeError"


def test_garbage_response_fails_open(tmp_path):
    c, _ = jev(tmp_path, FakeUrlopen({"answers": {"fit": {"choice": "maybe", "confidence": 1}}}))
    assert run(c.activity(WRITING, WindowInfo("helium", "a"))).reason.startswith("jev unavailable: unexpected")
    c2, _ = jev(tmp_path, FakeUrlopen({"nope": 1}))
    assert run(c2.activity(WRITING, WindowInfo("helium", "b"))).reason == "jev unavailable: no answers in response"


def notif_answer(action, conf, p_urgent):
    return {"model": "jev-1.14.0", "usage": {"input_tokens": 561, "output_tokens": 48},
            "answers": {"deliver": {"type": "choice", "choice": action, "confidence": conf},
                        "urgent": {"type": "noul", "noul": p_urgent}}}


def test_notification_one_request_two_questions(tmp_path):
    op = FakeUrlopen(notif_answer("hold", 0.8, 0.79))
    c, usage = jev(tmp_path, op)
    n = Notification("Slack", "Maya Chen", "can you sign off on the launch post? it goes out at 3")
    v = run(c.notification(WRITING, n))
    assert v.action == "hold" and v.time_sensitive and v.deadline is None
    assert v.reason == "needs action within the hour (p=0.79) · hold p=0.80 · jev"
    body = op.requests[0]["body"]
    assert set(body["questions"]) == {"deliver", "urgent"}
    assert body["questions"]["urgent"]["type"] == "noul" and "within the hour" in body["questions"]["urgent"]["instructions"]
    assert set(body["questions"]["deliver"]["criteria"]) == {"pass", "hold"}
    assert body["state"]["notification"]["body"].startswith("can you sign off")
    assert usage[0]["op"] == "notification" and usage[0]["input_tokens"] == 561
    cached = run(c.notification(WRITING, n))
    assert cached.cached and cached.time_sensitive and len(op.requests) == 1


def test_notification_low_confidence_passes_and_not_urgent(tmp_path):
    c, _ = jev(tmp_path, FakeUrlopen(notif_answer("hold", 0.2, 0.1)))
    v = run(c.notification(WRITING, Notification("Mail", "Newsletter", "")))
    assert v.action == "pass" and not v.time_sensitive and v.reason.startswith("low confidence (p=0.20 hold)")


def test_env_file_parsing(tmp_path):
    p = tmp_path / ".env"
    p.write_text('# secrets\nTYPESAFE_API_KEY="abc 123"\nexport OTHER=\'q\'\nPLAIN=v # note\n\nbroken line\nEMPTY=\n')
    assert load_env_file(p) == {"TYPESAFE_API_KEY": "abc 123", "OTHER": "q", "PLAIN": "v", "EMPTY": ""}
    assert load_env_file(tmp_path / "missing") == {}
    assert lookup("TYPESAFE_API_KEY", p, {}) == "abc 123"
    assert lookup("TYPESAFE_API_KEY", p, {"TYPESAFE_API_KEY": "from-env"}) == "from-env"
    assert lookup("NOPE", tmp_path / "missing", {}) == ""


def test_provider_selection(tmp_path, monkeypatch):
    cache = JsonFileCache(tmp_path / "c.json")
    missing = tmp_path / "missing.env"
    c, problem = pick_classifier(make_config(), cache, {}, missing)
    assert isinstance(c, ClaudeCliClassifier) and problem is None
    jev_cfg = make_config(llm_provider="jev", jev_model="jev-x", min_confidence=0.5)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    c, problem = pick_classifier(jev_cfg, cache, env_file=missing)
    assert isinstance(c, ClaudeCliClassifier) and problem == "TYPESAFE_API_KEY missing, falling back to claude"
    monkeypatch.setenv("TYPESAFE_API_KEY", "from-env")
    c, problem = pick_classifier(jev_cfg, cache, env_file=missing)
    assert isinstance(c, JevClassifier) and problem is None and c.model == "jev-x" and c.min_confidence == 0.5
    assert "from-env" not in repr(c)
    monkeypatch.delenv("TYPESAFE_API_KEY")
    (tmp_path / ".env").write_text("TYPESAFE_API_KEY=from-file\n")
    c, _ = pick_classifier(jev_cfg, cache, env_file=tmp_path / ".env")
    assert isinstance(c, JevClassifier)
    assert sync_classifier(c, make_config(llm_provider="jev", min_confidence=0.6)) is None and c.min_confidence == 0.6
    assert "restart" in sync_classifier(c, make_config())


def test_config_llm_keys(tmp_path):
    from lockdock.adapters.json_config import EXAMPLE, config_from_dict
    raw = json.loads(EXAMPLE.read_text())
    cfg = config_from_dict(raw)
    assert (cfg.llm_provider, cfg.jev_model, cfg.min_confidence) == ("claude", "jev-latest", 0.35)
    raw["llm"] = {"provider": "jev", "min_confidence": 0.5}
    assert config_from_dict(raw).llm_provider == "jev" and config_from_dict(raw).min_confidence == 0.5
    raw["llm"] = {"provider": "openai"}
    with pytest.raises(ValueError):
        config_from_dict(raw)


def test_classify_command(tmp_path):
    from lockdock.core.daemon import Daemon

    from .fakes import FakeClock, FakeConfigSource, FakePublisher, FakeRunner, FakeSink
    op = FakeUrlopen(choice("fit", "on", 0.9), choice("fit", "off", 0.8), choice("fit", "off", 0.9))
    c, _ = jev(tmp_path, op)
    d = Daemon(config_source=FakeConfigSource(make_config()), classifier=c, sink=FakeSink(),
               publisher=FakePublisher(), runner=FakeRunner(), clock=FakeClock())
    res = run(classify(d, {"cls": "helium", "title": "Rust Book", "mode": "building"}))
    assert res["verdict"] == "on" and res["source"] == "llm" and res["provider"] == "jev" and res["rules"] is None
    again = run(classify(d, {"cls": "helium", "title": "Rust Book", "mode": "building", "cached": True}))
    assert again["source"] == "cache" and len(op.requests) == 1
    fresh = run(classify(d, {"cls": "helium", "title": "Rust Book", "mode": "building"}))
    assert fresh["verdict"] == "off" and fresh["source"] == "llm" and len(op.requests) == 2
    ruled = run(classify(d, {"cls": "helium", "title": "youtube", "mode": "writing", "cached": True}))
    assert ruled["rules"]["verdict"] == "off" and len(op.requests) == 3
    assert "no mode" in run(classify(d, {"cls": "a", "title": "b", "mode": "nope"}))
