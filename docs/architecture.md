# lockdock architecture

The daemon is ports and adapters. `lockdock/core/` holds the logic and talks to
the world only through the Protocols in `core/ports.py`. `lockdock/adapters/`
holds the I/O. `lockdock/app.py` is the only place that wires one to the
other. No module in `core/` imports `adapters/` or starts a subprocess.

```
 Hyprland ─ HyprlandWindowSource ─┐                    ┌─ AtomicJsonStatePublisher ─ state.json ─ shell/
 busctl monitor ─ BusctlObserver ─┤                    ├─ BusctlNotificationSink ─ close / re-send
 modes.json ─ JsonConfigLoader ───┼─▶ core.Daemon ─────┼─ SubprocessCommandRunner ─ on_enter / on_exit
 unix socket ─ UnixSocketControl ─┤   ├ ModeManager    ├─ ClaudeCliClassifier ─ claude -p (+ JsonFileCache)
 /proc ─ ProcScanner ─────────────┘   ├ ActivityJudge  └─ EventLog ─ events.jsonl
                                      ├ NotificationGate
                                      └ AgentRegistry (feature: agents)
```

## Ports (`core/ports.py`)

| port | methods | adapter |
|---|---|---|
| `WindowSource` | `async watch(on_focus(WindowInfo))`, `current() -> WindowInfo` | `adapters/hyprland.py` `HyprlandWindowSource` (also `clients()`, `pid_for_class()`) |
| `UrlSource` | `async watch(on_url(browser_class, url))` | `adapters/http_url_source.py` `HttpUrlSource` (127.0.0.1 HTTP; fed by `browser-extension/`) |
| `NotificationObserver` | `async watch(on_notify(Notification), on_reply(cookie, id, sender))` | `adapters/dbus_notifications.py` `BusctlNotificationObserver` |
| `NotificationSink` | `close(id)`, `send(app, summary, body, desktop_entry="", urgency=1, timeout_ms=-1)` | `BusctlNotificationSink` |
| `Classifier` | `async activity(mode, window) -> (Verdict, reason)`, `async notification(mode, n) -> (action, reason)` | `adapters/claude_cli.py` `ClaudeCliClassifier` |
| `StatePublisher` | `publish(snapshot)` | `adapters/file_state.py` `AtomicJsonStatePublisher` |
| `CommandRunner` | `run(cmd)` | `adapters/shell_commands.py` `SubprocessCommandRunner` |
| `ConfigSource` | `load() -> Config`, `async watch(on_change, on_error=None)` | `adapters/json_config.py` `JsonConfigLoader` |
| `CommandHandler` | `handle(cmd, arg) -> result` | implemented by `core.daemon.Daemon`; served by `adapters/control_socket.py` |
| `Clock` | `now()`, `async sleep(s)` | `adapters/clock.py` `SystemClock` |
| `ProcessScanner` | `scan() -> list[ProcessInfo(pid, ppid, cmdline, cwd, cpu_s)]` | `adapters/proc_scan.py` `ProcScanner` (also `ancestor_pids()`) |

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
  one changes, dispatches control commands. `focus_listeners` get every focus
  change (`WindowInfo.address` is the Hyprland window address).
- `AgentRegistry` (`core/agents.py`, feature `features/agents.py`): the agent
  inbox. Merges `ProcessScanner` results (every 3 s; kinds from the
  data-driven `AgentKind` table, `DEFAULT_KINDS` + modes.json `agents.kinds`)
  with hook events (`lockdock agent-event`). A hook state beats the CPU-based
  scan guess; unseen for 10 s drops an agent, `done` ones stay 10 min;
  `needs_input` is sticky until a working/done event or until its window gets
  focus, and sends one desktop notification (tagged `x-lockdock`, so the
  NotificationGate never holds it). Window: walk the ppid chain to a Hyprland
  client pid. Merge logic for `lockdock agents install-hooks` is in
  `core/agent_hooks.py`.

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
| `browser` | `{enabled, url, connected, last_seen_ms}` from `features/browser_urls.py` |
| `agents` | `[{id, kind, label, state, since_ms, pid, cwd, window_address, last_message, session_id, glyph}]`, needs_input first, then working, idle, done. `state` is `working` / `needs_input` / `done` / `idle`; `id` is `<kind>:<pid>` (or `<kind>:<session>` for a hook-only agent) |
| `pet` | reserved: dict, empty until a feature registers it |
| `theme` | reserved: dict, empty until a feature registers it |
| `updated_ms` | write time |

`Daemon.window_enrichers` (callables `WindowInfo -> WindowInfo` applied on every focus
change) and `Daemon.on_url(browser, url)` (attach a URL to the focused browser window and re-judge)
let a UrlSource feature work without touching core.

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

Control verbs added by `features/agents.py`: `agent_event {kind, state, payload, pids}`,
`agent_focus <id>`, `agents`.

## Running a second instance for development

`LOCKDOCK_INSTANCE=dev ./bin/lockdock daemon` and
`LOCKDOCK_INSTANCE=dev qs -p ./shell` use `~/.config/lockdock-dev/`,
`~/.local/state/lockdock-dev/` and `$XDG_RUNTIME_DIR/lockdock-dev/`, so they
run beside the user's real daemon and dock. The CLI honours the same variable.
Note the dev dock still shows at the bottom-center and will visually overlap
the real one; stop the real dock first if you need a clean screenshot
(`pkill -f "[q]s -p \./shell$"`, and restart it afterwards).
