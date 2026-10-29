"""Optional features, discovered automatically.

Each module in this package may define

    def install(daemon: Daemon) -> list[Awaitable[None]]

which registers state sections / commands on the daemon and returns the
coroutines (watchers) the app should run alongside the core. Adding a feature
is adding a file here; app.py does not change.
"""
from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Awaitable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.daemon import Daemon


def install_all(daemon: Daemon) -> list[Awaitable[None]]:
    """Import every feature module and call its install(daemon)."""
    tasks: list[Awaitable[None]] = []
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda i: i.name):
        mod = importlib.import_module(f"{__name__}.{info.name}")
        install = getattr(mod, "install", None)
        if install:
            tasks.extend(install(daemon) or [])
    return tasks
