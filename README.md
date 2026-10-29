# lockdock

An AI-native dock for Hyprland with focus **modes** (Writing, Building, …).
A Linux take on [this macOS prototype](https://x.com/trq212/status/2115135857669881939).

- The dock shows the active mode, the other modes as small buttons, and the
  apps that belong to the mode (plus anything else running, dimmed).
- Leaving a mode has an **exit countdown**; every extra press cuts the wait.
- The daemon watches the focused window and judges it against the mode:
  rules first, then `claude -p --model haiku` for anything unknown. Off-task
  windows turn the dock red with a one-line reason.
- Notifications that do not belong to the mode are **held** (closed as they
  arrive, re-delivered when the mode ends). Keywords like "urgent" and
  critical urgency always pass.
- Modes live in one JSON file and the look in another (`theme.json`: position,
  scale, sections, autohide, ...); an agent edits them. See `AGENTS.md` and
  `skills/lockdock/`.

## Requirements

Hyprland, [Quickshell](https://quickshell.org) 0.3+, Python 3.11+, `busctl`
(systemd), and the `claude` CLI logged in (optional: set `llm.enabled: false`).
No API key: classification runs through your Claude Code login.

## Install

```
./scripts/install.sh      # links ~/.local/bin/lockdock, enables two user units
lockdock status
```

Or run the pieces by hand: `lockdock daemon` and `lockdock shell`.

## Use

```
lockdock mode writing     # switch (press again during a countdown to shorten it)
lockdock status           # mode, verdict for the current window, held count
lockdock held / release   # see or re-deliver held notifications
lockdock log -n 50        # every verdict with its reason
lockdock config           # path to modes.json
lockdock theme            # effective theme; `theme set <key> <json>`, `theme reset`, `theme path`
lockdock skill path       # the agent skill (also linked to ~/.claude/skills/lockdock)
```

## Layout

```
lockdock/             Python daemon + CLI (stdlib only), ports and adapters
  app.py              composition root: builds adapters, wires the Daemon, runs the loop
  core/               pure logic, no I/O besides events.jsonl
    models.py         Mode, Config, Verdict, WindowInfo, Notification, PendingSwitch
    ports.py          Protocol interfaces the adapters implement
    daemon.py         thin orchestrator; register_section / register_command
    modes.py          ModeManager: switching and the exit countdown
    activity.py       ActivityJudge: dwell, rules, classifier fallback
    notifications.py  NotificationGate: pass / hold / ask, release
    state.py          state.json snapshot (+ agents / pet / theme sections)
    theme.py          ThemeConfig (validated theme.json) and ThemeService
    rules.py events.py
  adapters/           hyprland, dbus_notifications (busctl), claude_cli (+cache),
                      json_config, file_state, control_socket, shell_commands, clock
  features/           optional features, auto-discovered (install(daemon))
  cli/                main.py (verbs), client.py (control socket client)
shell/                Quickshell dock (reads $XDG_RUNTIME_DIR/lockdock/state.json)
  Dock.qml            the panel window; builds the row from theme.sections
  components/         Theme (st.theme helper), ModeStrip, AppStrip, HeldBadge, Nudge, ModePill, AppButton
tests/                pytest with fakes for every port
docs/architecture.md  ports, adapters, state.json sections, how to add a feature
modes.example.json    default modes; copied to ~/.config/lockdock/modes.json
theme.example.json    default theme; copied to ~/.config/lockdock/theme.json
skills/lockdock/      agent skill: SKILL.md index + modes.md, theme.md, ...
```

Tests: `uv run --no-project --python 3.14 --with pytest pytest -q`

## Known limits

- A held notification is closed right after the daemon receives it, so the
  notification daemon may flash it for a frame. Owning the Notifications bus
  name ourselves would fix that but would replace your notification daemon.
- Window focus comes from Hyprland's event socket, so this does not work on
  other compositors yet (the dock itself is compositor-agnostic Quickshell).
