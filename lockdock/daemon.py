"""The lockdock daemon: one asyncio loop that owns mode state.

Inputs : Hyprland focus events, DBus notification traffic, modes.json edits,
         commands on a unix socket.
Outputs: $XDG_RUNTIME_DIR/lockdock/state.json (atomic; the dock watches it),
         events.jsonl (what was classified and why; the agent reads this to tune
         modes.json), notification holds/releases, on_enter/on_exit commands.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from dataclasses import dataclass, field

from . import classify, hypr, modes as modes_mod, notifications as notif
from .paths import EVENTS_LOG, MODES_FILE, SOCKET_FILE, STATE_FILE, ensure_dirs


@dataclass
class Pending:
    mode: str
    deadline: float
    total: float


@dataclass
class Daemon:
    cfg: modes_mod.Config
    mode: str = ""
    pending: Pending | None = None
    activity: dict = field(default_factory=dict)
    held: list[notif.Notification] = field(default_factory=list)
    # notifications we have decided to hold, keyed by (sender, cookie) until the id reply arrives
    _awaiting_id: dict[tuple[str, int], notif.Notification] = field(default_factory=dict)
    _focus: tuple[str, str] = ("", "")
    _dwell_task: asyncio.Task | None = None
    _mtime: float = 0.0
    _tick_task: asyncio.Task | None = None

    # ---------------- lifecycle ----------------
    async def run(self) -> None:
        ensure_dirs()
        classify.load_cache()
        classify.MODEL = self.cfg.llm_model
        self._mtime = MODES_FILE.stat().st_mtime
        self.mode = self.cfg.default_mode
        self._focus = hypr.active_window()
        self.write_state()
        self.schedule_classify()
        if SOCKET_FILE.exists():
            SOCKET_FILE.unlink()
        server = await asyncio.start_unix_server(self.handle_client, path=str(SOCKET_FILE))
        async with server:
            await asyncio.gather(
                hypr.watch_focus(self.on_focus),
                notif.watch(self.on_notify, self.on_reply),
                self.watch_modes_file(),
                server.serve_forever(),
            )

    def log(self, kind: str, **data) -> None:
        rec = {"ts": round(time.time(), 3), "kind": kind, "mode": self.mode, **data}
        with EVENTS_LOG.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    @property
    def cur(self) -> modes_mod.Mode:
        return self.cfg.get(self.mode) or self.cfg.modes[0]

    # ---------------- state file ----------------
    def write_state(self) -> None:
        st = {
            "mode": self.mode,
            "modes": [{"id": m.id, "label": m.label, "icon": m.icon, "color": m.color,
                       "apps": m.apps, "description": m.description} for m in self.cfg.modes],
            "pending": ({"mode": self.pending.mode, "deadline_ms": int(self.pending.deadline * 1000),
                         "total_ms": int(self.pending.total * 1000)} if self.pending else None),
            "activity": self.activity,
            "held": [n.short() for n in self.held[-50:]],
            "held_count": len(self.held),
            "updated_ms": int(time.time() * 1000),
        }
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False))
        os.replace(tmp, STATE_FILE)

    # ---------------- modes.json hot reload ----------------
    async def watch_modes_file(self) -> None:
        while True:
            await asyncio.sleep(2)
            try:
                mt = MODES_FILE.stat().st_mtime
            except OSError:
                continue
            if mt != self._mtime:
                self._mtime = mt
                self.reload()

    def reload(self) -> str:
        try:
            self.cfg = modes_mod.load()
        except (ValueError, KeyError, OSError) as e:
            self.log("config_error", error=str(e))
            return f"modes.json error: {e}"
        classify.MODEL = self.cfg.llm_model
        if not self.cfg.get(self.mode):
            self.mode = self.cfg.default_mode
        self.log("reload", modes=[m.id for m in self.cfg.modes])
        self.write_state()
        self.schedule_classify()
        return "reloaded"

    # ---------------- mode switching ----------------
    def request(self, mode_id: str) -> str:
        """A dock press / CLI call. Honours the exit countdown of the current mode."""
        target = self.cfg.get(mode_id)
        if not target:
            return f"unknown mode '{mode_id}'"
        if mode_id == self.mode:
            if self.pending:
                self.cancel_pending()
                return "cancelled pending switch"
            return f"already in {mode_id}"
        now = time.time()
        if self.pending and self.pending.mode == mode_id:
            cut = self.cur.per_press_s or 5
            self.pending.deadline = max(now, self.pending.deadline - cut)
            self.log("press", target=mode_id, remaining=round(self.pending.deadline - now, 1))
            if self.pending.deadline <= now:
                self.activate(mode_id)
                return f"switched to {mode_id}"
            self.write_state()
            return f"{self.pending.deadline - now:.0f}s left"
        delay = self.cur.exit_delay_s
        if delay <= 0:
            self.activate(mode_id)
            return f"switched to {mode_id}"
        self.pending = Pending(mode=mode_id, deadline=now + delay, total=delay)
        self.log("pending", target=mode_id, delay=delay)
        self.write_state()
        if self._tick_task:
            self._tick_task.cancel()
        self._tick_task = asyncio.get_running_loop().create_task(self._tick())
        return f"leaving {self.cur.label} in {delay}s (press again to cut {self.cur.per_press_s}s)"

    async def _tick(self) -> None:
        while self.pending:
            await asyncio.sleep(0.25)
            if self.pending and self.pending.deadline <= time.time():
                self.activate(self.pending.mode)

    def cancel_pending(self) -> None:
        self.pending = None
        self.log("cancel")
        self.write_state()

    def activate(self, mode_id: str) -> None:
        old, new = self.cur, self.cfg.get(mode_id)
        if not new:
            return
        self.pending = None
        for cmd in old.on_exit:
            subprocess.Popen(cmd, shell=True)
        self.mode = new.id
        self.log("switch", from_mode=old.id, to=new.id)
        for cmd in new.on_enter:
            subprocess.Popen(cmd, shell=True)
        self.release_held(f"while you were in {old.label}")
        self.write_state()
        self.schedule_classify()

    # ---------------- activity ----------------
    def on_focus(self, cls: str, title: str) -> None:
        self._focus = (cls, title)
        self.schedule_classify()

    def schedule_classify(self) -> None:
        if self._dwell_task:
            self._dwell_task.cancel()
        self._dwell_task = asyncio.get_running_loop().create_task(self._classify_after_dwell())

    async def _classify_after_dwell(self) -> None:
        await asyncio.sleep(self.cfg.dwell_s)
        cls, title = self._focus
        mode = self.cur
        if not cls:
            self.activity = {"verdict": "neutral", "reason": "no window", "app": "", "title": ""}
            self.write_state()
            return
        res = classify.rule_activity(mode, cls, title, self.cfg.browsers)
        if res is None:
            if self.cfg.llm_enabled:
                self.activity = {"verdict": "neutral", "reason": "classifying…", "app": cls, "title": title}
                self.write_state()
                res = await classify.llm_activity(mode, cls, title)
            else:
                res = ("neutral", "unknown app, llm disabled")
        if (cls, title) != self._focus:
            return  # focus moved on while we were thinking
        verdict, reason = res
        prev = self.activity.get("verdict")
        self.activity = {"verdict": verdict, "reason": reason, "app": cls, "title": title}
        self.log("activity", app=cls, title=title, verdict=verdict, reason=reason)
        if verdict == "off" and prev != "off" and mode.off_task_action == "notify":
            notif.send("lockdock", f"Off task in {mode.label}", f"{cls}: {title}\n{reason}", urgency=1,
                       timeout_ms=4000)
        self.write_state()

    # ---------------- notifications ----------------
    def on_notify(self, n: notif.Notification) -> None:
        mode = self.cur
        res = classify.rule_notification(mode, n.app, n.desktop_entry, n.summary, n.body, n.urgency)
        if res is None:
            # default == ask: decide via LLM; meanwhile close it as soon as the id arrives,
            # and re-send if the verdict is "pass".
            self._awaiting_id[(n.sender, n.cookie)] = n
            asyncio.get_running_loop().create_task(self._ask_notification(n))
            return
        action, reason = res
        self.log("notification", app=n.app, summary=n.summary, action=action, reason=reason)
        if action == "hold":
            self._awaiting_id[(n.sender, n.cookie)] = n
            self.held.append(n)
            self.write_state()

    async def _ask_notification(self, n: notif.Notification) -> None:
        action, reason = await classify.llm_notification(self.cur, n.app, n.summary, n.body)
        self.log("notification", app=n.app, summary=n.summary, action=action, reason=reason)
        if action == "pass":
            notif.send(n.app, n.summary, n.body, n.desktop_entry, n.urgency)
        else:
            self.held.append(n)
            self.write_state()

    def on_reply(self, cookie: int, nid: int, dest: str) -> None:
        n = self._awaiting_id.pop((dest, cookie), None)
        if n:
            n.id = nid
            notif.close(nid)

    def release_held(self, why: str) -> int:
        count = len(self.held)
        if not count:
            return 0
        if count <= 5:
            for n in self.held:
                notif.send(n.app, f"{n.summary}", f"{n.body}\n({why})", n.desktop_entry, n.urgency)
        else:
            apps: dict[str, int] = {}
            for n in self.held:
                apps[n.app] = apps.get(n.app, 0) + 1
            body = ", ".join(f"{a} ×{c}" for a, c in apps.items())
            notif.send("lockdock", f"{count} notifications held {why}", body, urgency=1)
        self.log("release", count=count)
        self.held.clear()
        self.write_state()
        return count

    # ---------------- control socket ----------------
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await reader.readline()
            req = json.loads(line or b"{}")
            cmd, arg = req.get("cmd"), req.get("arg")
            if cmd == "mode":
                out = self.request(arg)
            elif cmd == "cancel":
                self.cancel_pending(); out = "cancelled"
            elif cmd == "release":
                out = f"released {self.release_held('on request')}"
            elif cmd == "reload":
                out = self.reload()
            elif cmd == "status":
                out = json.loads(STATE_FILE.read_text())
            elif cmd == "reclassify":
                self.schedule_classify(); out = "scheduled"
            else:
                out = f"unknown command {cmd!r}"
            writer.write((json.dumps({"ok": True, "result": out}) + "\n").encode())
        except (json.JSONDecodeError, OSError) as e:
            writer.write((json.dumps({"ok": False, "error": str(e)}) + "\n").encode())
        finally:
            await writer.drain()
            writer.close()


def main() -> None:
    ensure_dirs()
    asyncio.run(Daemon(cfg=modes_mod.load()).run())
