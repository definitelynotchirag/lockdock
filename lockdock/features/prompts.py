"""Decision prompts: site cards, held-notification cards and verdict toasts in the dock.
Config: top-level `"prompts": {"enabled", "site_cards", "notification_cards", "verdict_toasts",
"stay_snooze_s"}` in modes.json. Logic in core/prompts.py."""
from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING

from ..core.prompts import PromptCenter

if TYPE_CHECKING:
    from ..core.daemon import Daemon

TICK_S = 1.0


async def _tick_loop(daemon: Daemon, center: PromptCenter) -> None:
    """Purge expired prompts once a second."""
    while True:
        await daemon.clock.sleep(TICK_S)
        center.tick()


def install(daemon: Daemon) -> list[Awaitable[None]]:
    """Register the `prompts` / `prompts_count` sections, the `prompts` and `prompt_act` commands."""
    center = PromptCenter(lambda: daemon.cfg, lambda: daemon.modes.cur, daemon.modes.request,
                          daemon.classifier, daemon.clock, daemon.events, daemon.publish, daemon.spawn)
    daemon.activity_listeners.append(center.on_activity)
    daemon.gate.hold_listeners.append(center.on_held)
    daemon.gate.release_listeners.append(center.on_released)
    daemon.switch_listeners.append(center.on_switch)
    daemon.register_section("prompts", center.snapshot)
    daemon.register_section("prompts_count", lambda: len(center.prompts))
    daemon.register_command("prompts", lambda _arg: center.snapshot())
    daemon.register_command("prompt_act", center.handle_act)
    return [_tick_loop(daemon, center)]
