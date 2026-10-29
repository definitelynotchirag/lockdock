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
```

## Layout

```
lockdock/        Python daemon + CLI (stdlib only)
  daemon.py      event loop: Hyprland focus, DBus notifications, modes.json watch, control socket
  classify.py    rules, then `claude -p` with a persistent cache
  notifications.py  busctl monitor parser, close/re-send
shell/           Quickshell dock (reads $XDG_RUNTIME_DIR/lockdock/state.json)
modes.example.json  default modes; copied to ~/.config/lockdock/modes.json
```

## Known limits

- A held notification is closed right after the daemon receives it, so the
  notification daemon may flash it for a frame. Owning the Notifications bus
  name ourselves would fix that but would replace your notification daemon.
- Window focus comes from Hyprland's event socket, so this does not work on
  other compositors yet (the dock itself is compositor-agnostic Quickshell).
