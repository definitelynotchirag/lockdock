import asyncio
import json

import pytest

from lockdock.adapters.http_url_source import HttpUrlSource
from lockdock.adapters.json_config import config_from_dict
from lockdock.core.activity import rule_activity
from lockdock.core.models import Verdict, WindowInfo
from lockdock.features.browser_urls import BrowserUrls, install

from .fakes import FakeUrlSource, make_config
from .test_daemon import make_daemon

EXT = "chrome-extension://abcdef"


async def http(port: int, raw: bytes) -> tuple[int, str, bytes]:
    r, w = await asyncio.open_connection("127.0.0.1", port)
    w.write(raw)
    await w.drain()
    data = await r.read()
    w.close()
    head, _, body = data.partition(b"\r\n\r\n")
    return int(head.split(b" ", 2)[1]) if head else 0, head.decode(errors="replace"), body


def post(body: bytes, extra: str = "", path: str = "/url") -> bytes:
    return (f"POST {path} HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n{extra}"
            f"Content-Length: {len(body)}\r\n\r\n").encode() + body


GOOD = json.dumps({"url": "https://reddit.com/r/rust", "title": "rust", "browser": "helium"}).encode()


async def with_server(token: str, fn):
    got: list[tuple[str, str]] = []
    src = HttpUrlSource(port=0, token=token)
    task = asyncio.create_task(src.watch(lambda b, u: got.append((b, u))))
    await src.started.wait()
    try:
        await fn(src.port, got)
    finally:
        task.cancel()


def run(token, fn):
    asyncio.run(with_server(token, fn))


def test_good_post_and_health():
    async def go(port, got):
        status, head, _ = await http(port, post(GOOD, f"Origin: {EXT}\r\n"))
        assert status == 204 and f"Access-Control-Allow-Origin: {EXT}" in head
        assert got == [("helium", "https://reddit.com/r/rust")]
        status, _, body = await http(port, b"GET /health HTTP/1.1\r\nHost: x\r\n\r\n")
        assert status == 200 and json.loads(body) == {"ok": True}
    run("", go)


def test_bad_json_and_garbage():
    async def go(port, got):
        assert (await http(port, post(b"{nope")))[0] == 400
        assert (await http(port, post(b'{"title": "no url"}')))[0] == 400
        assert (await http(port, post(b'{"url": 5}')))[0] == 400
        assert (await http(port, b"\x00\xff garbage\r\n\r\n"))[0] == 400
        assert (await http(port, b"POST /url HTTP/1.1\r\nContent-Length: abc\r\n\r\n"))[0] == 400
        assert (await http(port, b"POST /url HTTP/1.1\r\nContent-Length: 99999999\r\n\r\n"))[0] == 413
        assert got == []
        assert (await http(port, post(GOOD)))[0] == 204  # still serving
    run("", go)


def test_token_and_routing():
    async def go(port, got):
        assert (await http(port, post(GOOD)))[0] == 401
        assert (await http(port, post(GOOD, "Authorization: Bearer wrong\r\n")))[0] == 401
        assert got == []
        assert (await http(port, post(GOOD, "Authorization: Bearer s3cret\r\n")))[0] == 204
        assert len(got) == 1
        assert (await http(port, b"GET /url HTTP/1.1\r\n\r\n"))[0] == 405
        assert (await http(port, b"GET /nope HTTP/1.1\r\n\r\n"))[0] == 404
        assert (await http(port, post(GOOD, "Origin: https://evil.example\r\n")))[0] == 403
    run("s3cret", go)


def test_preflight():
    async def go(port, got):
        status, head, _ = await http(
            port, f"OPTIONS /url HTTP/1.1\r\nOrigin: {EXT}\r\nAccess-Control-Request-Method: POST\r\n\r\n".encode())
        assert status == 204 and "Authorization" in head and f"Allow-Origin: {EXT}" in head
    run("tok", go)


def test_rule_matches_url():
    cfg = make_config()
    mode = cfg.get("building")
    mode.off_task = [r"reddit\.com(?!/r/rust)"]
    mode.on_task = ["zed", r"docs\.rs"]
    b = cfg.browsers
    assert rule_activity(mode, WindowInfo("helium", "Home", "https://www.reddit.com/r/all"), b)[0] == Verdict.OFF
    assert rule_activity(mode, WindowInfo("helium", "Home", "https://www.reddit.com/r/rust"), b) is None
    assert rule_activity(mode, WindowInfo("helium", "Docs", "https://docs.rs/tokio"), b)[0] == Verdict.ON
    assert rule_activity(mode, WindowInfo("helium", "Docs"), b) is None  # no url: unchanged behaviour


def test_config_parsing():
    raw = {"modes": [{"id": "a"}], "browser_bridge": {"enabled": False, "port": 5, "token": "t"}}
    bb = config_from_dict(raw).browser_bridge
    assert (bb.enabled, bb.port, bb.token) == (False, 5, "t")
    bb = config_from_dict({"modes": [{"id": "a"}]}).browser_bridge
    assert (bb.enabled, bb.port, bb.token) == (True, 47231, "")


def test_rejudge_on_url_change(tmp_path):
    cfg = make_config(default_mode="building")
    cfg.get("building").off_task = [r"reddit\.com(?!/r/rust)"]
    d, pub, _, spawner = make_daemon(tmp_path, cfg)
    feature = BrowserUrls(d, FakeUrlSource([]))
    d.window_enrichers.append(feature.enrich)
    d.register_section("browser", feature.snapshot)
    d.start(WindowInfo("helium", "Reddit"))
    spawner.drain()
    d.on_focus(WindowInfo("helium", "Reddit"))
    spawner.drain()
    assert pub.snapshots[-1]["activity"].get("url") is None

    feature.on_url("helium", "https://reddit.com/r/all")
    spawner.drain()
    act = pub.snapshots[-1]["activity"]
    assert act["verdict"] == "off" and act["url"] == "https://reddit.com/r/all"

    feature.on_url("helium", "https://reddit.com/r/rust")
    spawner.drain()
    assert pub.snapshots[-1]["activity"]["verdict"] == "neutral"  # unknown -> classifier fake
    st = pub.snapshots[-1]["browser"]
    assert st["url"] == "https://reddit.com/r/rust" and st["connected"] is True

    # title change on the same tab keeps the URL
    d.on_focus(WindowInfo("helium", "Reddit - r/rust (2)"))
    assert d.judge.focus.url == "https://reddit.com/r/rust"
    spawner.discard()


def test_non_browser_focus_ignores_url(tmp_path):
    d, pub, _, spawner = make_daemon(tmp_path)
    feature = BrowserUrls(d)
    d.start(WindowInfo("kitty", "zsh"))
    spawner.drain()
    feature.on_url("helium", "https://reddit.com")
    assert d.judge.focus.url is None and not spawner.coros
    assert pub.snapshots[-1]["activity"].get("url") is None
    d.on_focus(WindowInfo("kitty", "zsh"))
    assert d.judge.focus.url is None
    spawner.discard()


def test_install_registers(tmp_path):
    d, pub, _, spawner = make_daemon(tmp_path)
    tasks = install(d)
    assert len(tasks) == 1
    tasks[0].close()
    assert d.handle("url", None)["connected"] is False
    d.publish()
    assert pub.snapshots[-1]["browser"]["url"] == ""

    d2, *_ = make_daemon(tmp_path, make_config(browser_bridge=config_from_dict(
        {"modes": [{"id": "a"}], "browser_bridge": {"enabled": False}}).browser_bridge))
    assert install(d2) == []


def test_busy_port_is_not_fatal(tmp_path):
    async def go():
        d, *_ = make_daemon(tmp_path)
        blocker = HttpUrlSource(port=0)
        t = asyncio.create_task(blocker.watch(lambda b, u: None))
        await blocker.started.wait()
        f = BrowserUrls(d, HttpUrlSource(port=blocker.port))
        await f.run()  # returns instead of raising
        t.cancel()
    asyncio.run(go())
