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
- **Agent inbox**: one chip per running coding agent (Claude Code, Codex,
  OpenCode, Aider, Gemini CLI, cursor-agent, T3 Code threads). Red and
  pulsing when it waits for you, green while it works, grey when done; click
  to focus its window. `lockdock agents install-hooks` wires Claude Code and
  Codex so the state is exact rather than guessed. See `skills/lockdock/agents.md`.
- Modes live in one JSON file that an agent edits. See `AGENTS.md`.

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
lockdock agents           # running coding agents and whether they need you
lockdock agents install-hooks --dry-run   # show the hook changes, then run without --dry-run
lockdock agent focus <id> # focus an agent's window
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
    agents.py         AgentRegistry: agent kinds table, scan + hook merge, window walk
    agent_hooks.py    install-hooks merge for Claude Code settings.json / Codex config.toml
    rules.py events.py
  adapters/           hyprland, dbus_notifications (busctl), claude_cli (+cache),
                      json_config, file_state, control_socket, shell_commands, clock, proc_scan
  features/           optional features, auto-discovered (install(daemon)); agents.py
  cli/                main.py (verbs), agents.py (agent verbs), client.py (control socket client)
shell/                Quickshell dock (reads $XDG_RUNTIME_DIR/lockdock/state.json)
  Dock.qml            the panel window; lays out components/ in one row
  components/         ModeStrip, AppStrip, AgentStrip, HeldBadge, Nudge, ModePill, AppButton
tests/                pytest with fakes for every port
docs/architecture.md  ports, adapters, state.json sections, how to add a feature
skills/lockdock/      pages for agents configuring lockdock (agents.md: the agent inbox)
modes.example.json    default modes; copied to ~/.config/lockdock/modes.json
```

Tests: `uv run --no-project --python 3.14 --with pytest pytest -q`

## Known limits

- A held notification is closed right after the daemon receives it, so the
  notification daemon may flash it for a frame. Owning the Notifications bus
  name ourselves would fix that but would replace your notification daemon.
- Window focus comes from Hyprland's event socket, so this does not work on
  other compositors yet (the dock itself is compositor-agnostic Quickshell).
