# lockdock architecture

The daemon is ports and adapters. `lockdock/core/` holds the logic and talks to
the world only through the Protocols in `core/ports.py`. `lockdock/adapters/`
holds the I/O. `lockdock/app.py` is the only place that wires one to the
other. No module in `core/` imports `adapters/` or starts a subprocess.

```
 Hyprland ─ HyprlandWindowSource ─┐                    ┌─ AtomicJsonStatePublisher ─ state.json ─ shell/
 busctl monitor ─ BusctlObserver ─┤                    ├─ BusctlNotificationSink ─ close / re-send
 modes.json ─ JsonConfigLoader ───┼─▶ core.Daemon ─────┼─ SubprocessCommandRunner ─ on_enter / on_exit
 unix socket ─ UnixSocketControl ─┤   ├ ModeManager    ├─ ClaudeCli/JevClassifier ─ claude -p | Jev HTTPS (+ JsonFileCache)
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
| `Classifier` | `async activity(mode, window) -> ActivityVerdict(verdict, reason, cached)`, `async notification(mode, n) -> NotificationVerdict(action, reason, time_sensitive, deadline, cached)` | `adapters/claude_cli.py` `ClaudeCliClassifier` (`claude -p`), or `adapters/jev.py` `JevClassifier` (TypeSafe AI `POST /v1/systemone`, stdlib urllib in a thread, 5 s timeout, one retry on 5xx/timeout, never raises: neutral / pass on failure; one `choice` question per window, a `choice` + `noul` pair per notification; `on_usage` logs `kind: "classifier"`). Both share `JsonFileCache` and its keys (`activity_key`, `notification_key`). `app.pick_classifier` chooses by `llm.provider` once at startup (key: `TYPESAFE_API_KEY` from the environment or `paths.ENV_FILE` via `adapters/env_file.py`; missing key -> Claude + `config_error`); a provider change needs a restart. The pet `Speaker` is always Claude |
| `StatePublisher` | `publish(snapshot)` | `adapters/file_state.py` `AtomicJsonStatePublisher` |
| `CommandRunner` | `run(cmd)` | `adapters/shell_commands.py` `SubprocessCommandRunner` |
| `ConfigSource` | `load() -> Config`, `async watch(on_change, on_error=None)` | `adapters/json_config.py` `JsonConfigLoader` (generic: `parse=` builds another type, `update(changes)` rewrites keys; pet.json uses it too) (built on `JsonFileWatcher`; generic: `parse=` builds another type, `update(changes)` rewrites keys; pet.json uses it too) |
| `JsonDocument` | `read()`, `write(raw)`, `async watch(on_change, on_error=None)` | `adapters/json_config.py` `JsonFileWatcher` (mtime polling, seeded from an example file, atomic writes; `JsonConfigLoader` is built on it) |
| `CommandHandler` | `handle(cmd, arg) -> result` | implemented by `core.daemon.Daemon`; served by `adapters/control_socket.py` |
| `Clock` | `now()`, `async sleep(s)` | `adapters/clock.py` `SystemClock` |
| `ProcessScanner` | `scan() -> list[ProcessInfo(pid, ppid, cmdline, cwd, cpu_s)]` | `adapters/proc_scan.py` `ProcScanner` (also `ancestor_pids()`) |
| `Speaker` | `async line(mood, mode, app, title, reason) -> str \| None` | `adapters/claude_cli.py` `ClaudeCliSpeaker` (one line of at most 12 words in the pet.json `persona`, cached per (mood, app)) |
| `PetPackSource` | `resolve(name) -> (pack_dir, manifest) \| None`, `available() -> [{name, title, author, source, dir}]` | `adapters/pet_packs.py` `DirPetPacks` (user `~/.config/lockdock/pets/` before built-in `shell/pets/`) |
| `PaletteSource` | `material() -> (roles, origin) \| None`, `prefers_dark()`, `async watch(on_change)` | `adapters/system_palette.py` `MatugenPaletteSource` (first existing of `paths.PALETTE_FILES`: `~/.config/lockdock/colors.json`, then end-4's `~/.local/state/quickshell/user/generated/colors.json`; mtime polling) with `GsettingsSchemeProbe` (`color-scheme`; dark if gsettings is missing) |

Fakes for every port are in `tests/fakes.py`.

## Core services

- `ModeManager` (`core/modes.py`): current mode, `request()` (the dock press),
  exit countdown, `press` math, `cancel`, `activate` (runs on_exit / on_enter).
- `ActivityJudge` (`core/activity.py`): `rule_activity()` then the classifier,
  after `dwell_s`; drops a verdict if focus moved on meanwhile. The activity
  carries `source`: `rule`, `llm` (a live classifier call) or `cache`.
- `NotificationGate` (`core/notifications.py`): `decide()` -> pass / hold /
  ask, the held list, `release_messages()` (<= 5 one by one, else a summary).
  `hold_listeners(n, NotificationVerdict | None)` hear every held notification.
- `PromptCenter` (`core/prompts.py`, feature `features/prompts.py`): decision
  cards. Inputs: `activity_listeners` (site cards via `belongs_to()`, verdict
  toasts for `source == "llm"`), `gate.hold_listeners` (notification cards via
  `held_for()`; a tag call to the classifier when the gate did not ask one),
  `Daemon.switch_listeners` (a switch clears cards and snoozes), a 1 s tick
  (expiry). `switch` is `ModeManager.request`, so it starts or presses the
  countdown. Config: `Config.prompts` (`PromptsConfig`). Every open / act /
  expire / drop / tag is logged as `kind: "prompt"` with `op`.
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
  one changes, dispatches control commands. `activity_listeners` get the
  activity dict plus `mode` (the mode label) after every final verdict.
- `PetBrain` (`core/pet.py`, wired by `features/pet.py`): verdicts and a 1 s
  tick in, mood / scale / speech line out. `off_seconds` rises while off task
  and decays `decay_per_s` times as fast otherwise; moods come from
  `thresholds`; growth (0..1) rises over `grow_s` while furious and off task,
  falls over `shrink_s` otherwise. Config: `~/.config/lockdock/pet.json`
  (seeded from `pet.example.json`, hot-reloaded). Control verb: `pet [status |
  calm | mood <m>|auto | mute | unmute | pack <name> | packs | say <text>]`.

## state.json

Written atomically to `$XDG_RUNTIME_DIR/lockdock/state.json` on every change.

| key | content |
|---|---|
| `mode` | active mode id |
| `modes` | `[{id, label, icon, color, apps, description, notifications}]`; `notifications` is the mode's default notification policy (`pass` / `hold` / `ask`) |
| `pending` | `{mode, deadline_ms, total_ms}` or `null` |
| `activity` | `{verdict, reason, app, title, source}` (+ `url` when a UrlSource supplied one); `source` is `rule` / `llm` / `cache` |
| `held` | last 50 held notifications `{app, summary, body, urgency, ts, id}` |
| `held_count` | number held |
| `browser` | `{enabled, url, connected, last_seen_ms}` from `features/browser_urls.py` |
| `agents` | `[{id, kind, label, state, since_ms, pid, cwd, window_address, last_message, session_id, glyph}]`, needs_input first, then working, idle, done. `state` is `working` / `needs_input` / `done` / `idle`; `id` is `<kind>:<pid>` (or `<kind>:<session>` for a hook-only agent) |
| `pet` | `{name, mood, scale, line, line_id, off_seconds, pack, pack_dir, manifest, size, muted, forced, position, max_screen_fraction}` from `features/pet.py`. `mood` is content / suspicious / annoyed / furious; `scale` is the size in dock sprites (1.0 = in the dock; the overlay shows above 1.05, capped at `max_screen_fraction` of the screen); `line_id` bumps on every new line; `manifest` is the pack's `pack.json`, frames relative to `pack_dir`; `forced` is a previewed mood or null |
| `theme` | the effective theme (`features/theme.py`; see `ThemeConfig.snapshot()` in `core/theme.py`) plus `colors` (the resolved palette: `{bg, bg_elevated, surface, surface_hover, text, text_muted, outline, accent, on_accent, accent_container, on_accent_container, secondary, tertiary, danger, on_danger, success, warning, bubble, bubble_text, shadow}` as `#AARRGGBB`) and `palette_source` (file path or built-in fallback); `{}` without the feature |
| `prompts` | open decision cards, newest last, at most 3: `[{id, kind, created_ms, expires_ms, icon, title, subtitle, body, tag, actions}]`. `kind` is `notification` / `site` / `verdict`; `expires_ms` is null (stays until acted on) or a time (verdict toasts: created + 6 s); `tag` is `{label, detail, level}` (`level` `urgent` / `info` / `ok`) or null; `actions` are `[{id, label, style, mode?}]` with `id` `later` / `stay` / `switch` (switch has `mode`) and `style` `plain` / `primary`; verdict toasts have none. `[]` without the feature |
| `prompts_count` | number of open prompts |
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
   `daemon.config_listeners.append(...)` / `daemon.activity_listeners.append(...)`,
   and returns watcher coroutines.
   `features.install_all` discovers the module; `app.py` stays untouched.
   Call `daemon.publish()` from the service's `on_change`.
4. **Shell component.** Add `shell/components/<Thing>.qml` taking
   `required property var st` (the state) and `required property var theme`
   (see below), and register it in `Dock.qml`'s `sectionMap` (one line:
   `pet: petComp,` after adding a `Component { id: petComp; Pet { ... } }`).
   Users then place it with `theme.sections`. Components that float outside
   the card (like `Nudge`) are anchored to `card` and added to the `mask`
   Region instead. A section with a pop-up registers itself on the dock
   (`petItem`, `agentsPill`) so the dock can add the pop-up to the `mask` and
   to `implicitHeight` (the window's headroom); `AgentsPanel` lives in
   `Dock.qml` next to `Nudge` and is placed from the pill's centre. Read your section as `st.<name>`.

Shell components outside the section row: `Nudge` (off-task bubble), `AgentsPanel` (the
agents list) and `PromptStack` (decision cards from `st.prompts`: one `PromptCard` per
prompt, newest nearest the dock, at most `theme.prompts.max_visible`). The stack keeps a
`ListModel` synced by prompt id so cards animate in and out across state.json rewrites, hides a
prompt past its `expires_ms`, and on a button sends `["prompt", id, action]` and hides the
card at once. `Dock.qml` adds it to the `mask` and reserves `promptsHeadroom` (room for
`max_visible` tall cards) while any card is up. `ModeStrip` shows the pending switch as a
timer pill (click = `["mode", target]`, press again) and a Stay pill (`["cancel"]`,
`theme.mode_strip.stay_button`).
5. **Tests.** `tests/test_<feature>.py` with the fakes;
   `uv run --no-project --python 3.14 --with pytest pytest -q`.

Control verbs may return an awaitable; `UnixSocketControl` awaits it before replying
(`features/classify.py`: `classify {cls, title, mode?, url?, cached?}` runs the classifier once and
returns `{mode, provider, verdict, reason, source, ms, rules}`).

`features/theme.py` adds `pin` (arg `on` / `off` / `toggle`).
Control verbs added by `features/agents.py`: `agent_event {kind, state, payload, pids}`,
`agent_focus <id>`, `agents`. By `features/prompts.py`: `prompts` (the list) and
`prompt_act {id, action}` with action `later` / `dismiss` (close), `stay` (close and
snooze that host for `prompts.stay_snooze_s`), `switch` (close and request the mode).

## Theme and dock sections

`theme.json` (`features/theme.py`, `core/theme.py`) is the single place for the
dock's look; `ThemeService` validates it, writes it (`theme_set`, `theme_reset`
commands) and publishes `st.theme`. Colours come from `core/palette.py`:
`resolve(theme.palette, material, origin, prefers_dark)` maps the desktop's
Material You roles (`Palette.from_material`) or picks the built-in `DARK` /
`LIGHT`, then merges role overrides; `ThemeService.refresh_palette()` runs when
the `PaletteSource` reports an edit and republishes only on a real change.

In the shell, `components/Theme.qml` wraps `st.theme` with typed properties
that all have fallbacks (a missing key never breaks the dock). Use
`theme.px(n)` for sizes (applies `scale`), `theme.ipx(n)` for sizes that
should also follow `icon_size`, `theme.fpx(n)` for font pixel sizes, and
`theme.family` for `font.family`. Colours are palette roles (`theme.bg`,
`theme.text`, `theme.textMuted`, `theme.surfaceHover`, `theme.paletteAccent`,
`theme.accentContainer` / `theme.accentContainerInk`, `theme.danger` /
`theme.dangerInk`, `theme.bubble`, ...; never a literal colour, and never a
property named `onX`, which QML reads as a signal handler). `theme.modeColor(mode)`
resolves a mode's `"auto"` colour.

Icons: `components/Icon.qml` (`name`, `color`, `size`, `stroke`, `family`) draws
`icona:<slug>` from `shell/icons/icona/<slug>.svg` (read with `FileView`,
`currentColor` and the stroke width replaced, passed to an `Image` as a `data:` URL,
rasterised at the drawn size), a freedesktop icon name (`IconImage`), or a text
glyph / emoji (`Text`); an unknown slug draws a dot and logs once. Never hard-code
a glyph: take the name from `theme.icon(key, fallback)` (theme.json `icons`,
`IconsTheme` in `core/theme.py`, add a key there and to `theme.example.json`),
`theme.modeIcon(mode)` or `theme.agentIcon(agent)`, and pass
`stroke: theme.iconStroke`. `components/Island.qml` is the rounded,
bordered, shadowed surface used by every island, the slab card and the nudge.
Pass the `theme` object down to components.

`Dock.qml` groups `theme.sections` into `groups` (layout `islands`: one group
per section, sections in `joinSections` (the pet) share their neighbour's
island; layout `slab`: one group) and renders one `Island` per group, each id
looked up in `sectionMap` and loaded with a `Loader`. Unknown ids render nothing, ids that
are not listed are hidden. A section component may expose
`readonly property bool active` (default true) to say it has nothing to show,
which also drops its divider. List a section in `inlineSections` to draw it
without a divider (like the held badge). To add a section: one `Component` and
one `sectionMap` entry; also add its id to `DEFAULT_SECTIONS` in
`core/theme.py` and `theme.example.json` if it should show by default.

Interaction: every clickable thing is a `components/Pressable.qml` (use it as the root
of a button or pill, like a MouseArea that animates). It exposes `hovered`, `pressed`,
`clicked()`, `hoverProgress` (0..1, 180 ms OutCubic in, 240 ms out), `pressProgress`
(80 ms in, 160 ms OutBack out), `pressScale` (bind `scale: pressScale`) and `lift(px)` (an
icon's hover translate). Draw hover as a `surface_hover` fill at `hoverProgress`, not with a
`Behavior` on a colour (it would chase every frame). Durations go through
`theme.dur(ms)`, which is 0 under `theme.reduced_motion`. Its `tip: {icon, title,
detail}` is the tooltip: Pressable calls `theme.host.showTip(item, tip)` /
`hideTip(item)`; `theme.host` is the Dock (`Theme { host: dock }`), which owns the one
`components/Tip.qml` per window. The Dock waits `theme.tooltipDelayMs` (switching at once
while a tip shows or just faded), places the tip above the item (below at the top; flipped
if it does not fit, clamped to the window, the tail on the item's centre; an item on the
islands points at the island edge), adds it to the `mask` only while visible, and always
reserves `tipHeadroom` (and a tip's height over the agents list) so hovering never resizes
the layer surface. Never use `QtQuick.Controls` `ToolTip`.

Pinning: `theme.pinned` sets `exclusiveZone` to `reservedZone` (`islandHeight + margin`:
the island row only, never the transparent headroom for cards, bubbles and tips), else 0
(or -1 with autohide). Pinned forces autohide off (`Dock.autohide`). The `pin` control verb
(`ThemeService.pin`: on / off / toggle, written through `set`) backs `lockdock pin`,
`unpin`, `pin toggle` and the optional `"pin"` section (`components/PinButton.qml`, in
`inlineSections` and `joinSections`, not in `DEFAULT_SECTIONS`).

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
