"""Mode switching with an exit countdown that every extra press shortens."""
from __future__ import annotations

import asyncio
from collections.abc import Callable

from .events import EventSink
from .models import Config, Mode, PendingSwitch
from .ports import Clock, CommandRunner
from .tasks import Spawn, spawn_task

TICK_S = 0.25


class ModeManager:
    """Owns the current mode and a pending switch.

    `on_switch(old, new)` fires after a switch; `on_change()` fires whenever the
    published state (mode or pending) changed without a switch.
    """

    def __init__(self, config: Callable[[], Config], clock: Clock, runner: CommandRunner,
                 events: EventSink, on_switch: Callable[[Mode, Mode], None],
                 on_change: Callable[[], None], spawn: Spawn = spawn_task) -> None:
        self._config = config
        self.clock = clock
        self.runner = runner
        self.events = events
        self.on_switch = on_switch
        self.on_change = on_change
        self.spawn = spawn
        self.mode: str = config().default_mode
        self.pending: PendingSwitch | None = None
        self._tick_task: asyncio.Task[None] | None = None

    @property
    def cfg(self) -> Config:
        return self._config()

    @property
    def cur(self) -> Mode:
        """The active mode (falls back to the first mode if the id vanished)."""
        return self.cfg.get(self.mode) or self.cfg.modes[0]

    def config_changed(self) -> None:
        """After a reload: fall back to the default mode if ours was removed."""
        if not self.cfg.get(self.mode):
            self.mode = self.cfg.default_mode

    def request(self, mode_id: str) -> str:
        """A dock press / CLI call. Honours the exit countdown of the current mode."""
        if not self.cfg.get(mode_id):
            return f"unknown mode '{mode_id}'"
        if mode_id == self.mode:
            if self.pending:
                self.cancel()
                return "cancelled pending switch"
            return f"already in {mode_id}"
        now = self.clock.now()
        if self.pending and self.pending.mode == mode_id:
            return self.press(mode_id, now)
        delay = self.cur.exit_delay_s
        if delay <= 0:
            self.activate(mode_id)
            return f"switched to {mode_id}"
        self.pending = PendingSwitch(mode=mode_id, deadline=now + delay, total=delay)
        self.events.log("pending", target=mode_id, delay=delay)
        self.on_change()
        if self._tick_task:
            self._tick_task.cancel()
        self._tick_task = self.spawn(self._countdown())
        return f"leaving {self.cur.label} in {delay}s (press again to cut {self.cur.per_press_s}s)"

    def press(self, mode_id: str, now: float) -> str:
        """An extra press on the pending target: cut the wait by per_press_s (default 5)."""
        assert self.pending
        cut = self.cur.per_press_s or 5
        self.pending.deadline = max(now, self.pending.deadline - cut)
        self.events.log("press", target=mode_id, remaining=round(self.pending.deadline - now, 1))
        if self.pending.deadline <= now:
            self.activate(mode_id)
            return f"switched to {mode_id}"
        self.on_change()
        return f"{self.pending.deadline - now:.0f}s left"

    def poll(self) -> None:
        """Activate the pending switch if its deadline passed."""
        if self.pending and self.pending.deadline <= self.clock.now():
            self.activate(self.pending.mode)

    async def _countdown(self) -> None:
        while self.pending:
            await self.clock.sleep(TICK_S)
            self.poll()

    def cancel(self) -> None:
        """Drop a pending switch (logged even when there was none)."""
        self.pending = None
        self.events.log("cancel")
        self.on_change()

    def activate(self, mode_id: str) -> None:
        """Switch now: run on_exit, change mode, run on_enter, then notify listeners."""
        old, new = self.cur, self.cfg.get(mode_id)
        if not new:
            return
        self.pending = None
        for cmd in old.on_exit:
            self.runner.run(cmd)
        self.mode = new.id
        self.events.log("switch", from_mode=old.id, to=new.id)
        for cmd in new.on_enter:
            self.runner.run(cmd)
        self.on_switch(old, new)
