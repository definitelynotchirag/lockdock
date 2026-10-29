# lockdock architecture

The daemon is ports and adapters. `lockdock/core/` holds the logic and talks to
the world only through the Protocols in `core/ports.py`. `lockdock/adapters/`
holds the I/O. `lockdock/app.py` is the only place that wires one to the
other. No module in `core/` imports `adapters/` or starts a subprocess.

```
 Hyprland ─ HyprlandWindowSource ─┐                    ┌─ AtomicJsonStatePublisher ─ state.json ─ shell/
 busctl monitor ─ BusctlObserver ─┤                    ├─ BusctlNotificationSink ─ close / re-send
 modes.json ─ JsonConfigLoader ───┼─▶ core.Daemon ─────┼─ SubprocessCommandRunner ─ on_enter / on_exit
 unix socket ─ UnixSocketControl ─┘   ├ ModeManager    ├─ ClaudeCliClassifier ─ claude -p (+ JsonFileCache)
                                      ├ ActivityJudge  └─ EventLog ─ events.jsonl
                                      └ NotificationGate
```

## Ports (`core/ports.py`)

| port | methods | adapter |
|---|---|---|
| `WindowSource` | `async watch(on_focus(WindowInfo))`, `current() -> WindowInfo` | `adapters/hyprland.py` `HyprlandWindowSource` (also `clients()`, `pid_for_class()`) |
| `UrlSource` | `async watch(on_url(browser_class, url))` | none yet |
| `NotificationObserver` | `async watch(on_notify(Notification), on_reply(cookie, id, sender))` | `adapters/dbus_notifications.py` `BusctlNotificationObserver` |
| `NotificationSink` | `close(id)`, `send(app, summary, body, desktop_entry="", urgency=1, timeout_ms=-1)` | `BusctlNotificationSink` |
| `Classifier` | `async activity(mode, window) -> (Verdict, reason)`, `async notification(mode, n) -> (action, reason)` | `adapters/claude_cli.py` `ClaudeCliClassifier` |
| `StatePublisher` | `publish(snapshot)` | `adapters/file_state.py` `AtomicJsonStatePublisher` |
| `CommandRunner` | `run(cmd)` | `adapters/shell_commands.py` `SubprocessCommandRunner` |
| `ConfigSource` | `load() -> Config`, `async watch(on_change, on_error=None)` | `adapters/json_config.py` `JsonConfigLoader` |
| `JsonDocument` | `read()`, `write(raw)`, `async watch(on_change, on_error=None)` | `adapters/json_config.py` `JsonFileWatcher` (mtime polling, seeded from an example file, atomic writes; `JsonConfigLoader` is built on it) |
| `CommandHandler` | `handle(cmd, arg) -> result` | implemented by `core.daemon.Daemon`; served by `adapters/control_socket.py` |
| `Clock` | `now()`, `async sleep(s)` | `adapters/clock.py` `SystemClock` |

Fakes for every port are in `tests/fakes.py`.

## Core services

- `ModeManager` (`core/modes.py`): current mode, `request()` (the dock press),
  exit countdown, `press` math, `cancel`, `activate` (runs on_exit / on_enter).
- `ActivityJudge` (`core/activity.py`): `rule_activity()` then the classifier,
  after `dwell_s`; drops a verdict if focus moved on meanwhile.
- `NotificationGate` (`core/notifications.py`): `decide()` -> pass / hold /
  ask, the held list, `release_messages()` (<= 5 one by one, else a summary).
- `StateSnapshot` (`core/state.py`) and `EventLog` (`core/events.py`).
- `Daemon` (`core/daemon.py`): owns the above, publishes a snapshot whenever
  one changes, dispatches control commands.

## state.json

Written atomically to `$XDG_RUNTIME_DIR/lockdock/state.json` on every change.

| key | content |
|---|---|
| `mode` | active mode id |
| `modes` | `[{id, label, icon, color, apps, description}]` |
| `pending` | `{mode, deadline_ms, total_ms}` or `null` |
| `activity` | `{verdict, reason, app, title}` (+ `url` when a UrlSource supplied one) |
| `held` | last 50 held notifications `{app, summary, body, urgency, ts, id}` |
| `held_count` | number held |
| `agents` | reserved: list, empty until a feature registers it |
| `pet` | reserved: dict, empty until a feature registers it |
| `theme` | the effective theme (`features/theme.py`; see `ThemeConfig.snapshot()` in `core/theme.py`); `{}` without the feature |
| `updated_ms` | write time |

`Daemon.register_section(name, provider)` makes `provider()` (a dict or list)
appear under `name` in every snapshot. Core keys cannot be overridden.

## How to add a feature

1. **Core service.** Put the logic in a new `lockdock/core/<feature>.py`. Take
   ports and callbacks in the constructor (see `NotificationGate`), call an
   `on_change` callback when its published data changes.
2. **Adapter.** If it needs I/O, define or reuse a Protocol in
   `core/ports.py` and implement it in `lockdock/adapters/<thing>.py`. Add a
   fake to `tests/fakes.py`.
3. **Wire it.** Add `lockdock/features/<feature>.py` with
   `install(daemon) -> list[Awaitable[None]]`. It builds the adapter and the
   service, calls `daemon.register_section("agents", service.snapshot)`,
   optionally `daemon.register_command("verb", fn)` and
   `daemon.config_listeners.append(...)`, and returns watcher coroutines.
   `features.install_all` discovers the module; `app.py` stays untouched.
   Call `daemon.publish()` from the service's `on_change`.
4. **Shell component.** Add `shell/components/<Thing>.qml` taking
   `required property var st` (the state) and `required property var theme`
   (see below), and register it in `Dock.qml`'s `sectionMap` (one line:
   `pet: petComp,` after adding a `Component { id: petComp; Pet { ... } }`).
   Users then place it with `theme.sections`. Components that float outside
   the card (like `Nudge`) are anchored to `card` and added to the `mask`
   Region instead. Read your section as `st.<name>`.
5. **Tests.** `tests/test_<feature>.py` with the fakes;
   `uv run --no-project --python 3.14 --with pytest pytest -q`.

## Theme and dock sections

`theme.json` (`features/theme.py`, `core/theme.py`) is the single place for the
dock's look; `ThemeService` validates it, writes it (`theme_set`, `theme_reset`
commands) and publishes `st.theme`. Defaults reproduce the original look.

In the shell, `components/Theme.qml` wraps `st.theme` with typed properties
that all have fallbacks (a missing key never breaks the dock). Use
`theme.px(n)` for sizes (applies `scale`), `theme.ipx(n)` for sizes that
should also follow `icon_size`, `theme.fpx(n)` for font pixel sizes, and
`theme.family` for `font.family`. Pass the `theme` object down to components.

`Dock.qml` renders `theme.sections` with a `Repeater`; each id is looked up in
`sectionMap` and loaded with a `Loader`. Unknown ids render nothing, ids that
are not listed are hidden. A section component may expose
`readonly property bool active` (default true) to say it has nothing to show,
which also drops its divider. List a section in `inlineSections` to draw it
without a divider (like the held badge). To add a section: one `Component` and
one `sectionMap` entry; also add its id to `DEFAULT_SECTIONS` in
`core/theme.py` and `theme.example.json` if it should show by default.

Do not position things with `anchors.x: cond ? a : undefined` in QML: an
anchor, once set, is not reset by a later `undefined`. Bind `y`/`x` instead.

## Running a second instance for development

`LOCKDOCK_INSTANCE=dev ./bin/lockdock daemon` and
`LOCKDOCK_INSTANCE=dev qs -p ./shell` use `~/.config/lockdock-dev/`,
`~/.local/state/lockdock-dev/` and `$XDG_RUNTIME_DIR/lockdock-dev/`, so they
run beside the user's real daemon and dock. The CLI honours the same variable.
Note the dev dock still shows at the bottom-center and will visually overlap
the real one; stop the real dock first if you need a clean screenshot
(`pkill -f "[q]s -p \./shell$"`, and restart it afterwards), or move the dev
dock with its theme (`LOCKDOCK_INSTANCE=dev lockdock theme set margin 300`).
Pick a unique instance name when other agents may be testing at the same time:
instances with the same name share one socket and state file. Quickshell does
not always hot-reload QML: restart the dev dock after editing it.
