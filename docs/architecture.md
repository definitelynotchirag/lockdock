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
| `theme` | reserved: dict, empty until a feature registers it |
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
   `required property var st` (the state) and place it in `Dock.qml`'s `row`
   (or anchored to `card`, like `Nudge`; add it to the `mask` Region if it sits
   outside the card). Read your section as `st.<name>`.
5. **Tests.** `tests/test_<feature>.py` with the fakes;
   `uv run --no-project --python 3.14 --with pytest pytest -q`.

## Running a second instance for development

`LOCKDOCK_INSTANCE=dev ./bin/lockdock daemon` and
`LOCKDOCK_INSTANCE=dev qs -p ./shell` use `~/.config/lockdock-dev/`,
`~/.local/state/lockdock-dev/` and `$XDG_RUNTIME_DIR/lockdock-dev/`, so they
run beside the user's real daemon and dock. The CLI honours the same variable.
Note the dev dock still shows at the bottom-center and will visually overlap
the real one; stop the real dock first if you need a clean screenshot
(`pkill -f "[q]s -p \./shell$"`, and restart it afterwards).
