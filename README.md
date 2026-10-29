# lockdock

An AI-native dock for Hyprland with focus **modes** (Writing, Building, …).
A Linux take on [this macOS prototype](https://x.com/trq212/status/2115135857669881939).

- The dock shows the active mode, the other modes as small buttons, and the
  apps that belong to the mode (plus anything else running, dimmed).
- Leaving a mode has an **exit countdown**; every extra press cuts the wait.
  While it runs the dock shows a timer pill ("Social 0:10") and a **Stay**
  button that cancels the switch.
- **Decision cards** float above the dock when something needs a choice: a
  held message that looks urgent, a site that belongs to another mode
  ([Stay] / [Go to Social (15s wait)]), or a short toast with the verdict on an
  unknown site. Theme key `prompts` (see `skills/lockdock/theme.md`).
- The daemon watches the focused window and judges it against the mode:
  rules first, then `claude -p --model haiku` for anything unknown. Off-task
  windows turn the dock red with a one-line reason.
- Notifications that do not belong to the mode are **held** (closed as they
  arrive, re-delivered when the mode ends). Keywords like "urgent" and
  critical urgency always pass.
- **Decision cards**: when a window belongs to another mode ("x.com · belongs
  to Social"), the dock asks *Stay* or *Go to Social (30s wait)*; a held
  notification gets a card with *Later* / *Go to X* and a "Time-sensitive" tag
  when the classifier sees someone waiting; a fresh LLM verdict on a site no
  mode knows shows as a toast that fades. "Go to X" is the normal exit
  countdown. `lockdock prompts`, `lockdock prompt <id> <action>`.
- **Agent inbox**: one pill for every running coding agent (Claude Code, Codex,
  OpenCode, Aider, Gemini CLI, cursor-agent, T3 Code threads). Red and
  pulsing when one waits for you, green while they work, grey when done; click
  it for the list, click a row to focus that agent's window (theme
  `agents.style: "chips"`: one chip per agent instead). `lockdock agents install-hooks` wires Claude Code and
  Codex so the state is exact rather than guessed. See `skills/lockdock/agents.md`.
- A **pixel cat** lives in the dock. It is content while you are on task, then
  suspicious, annoyed and furious the longer you stay off task, and says so in
  a speech bubble. Keep ignoring it and it grows into a click-through overlay
  that fills most of the screen; go back to the task and it shrinks right away.
  Click it to calm it. Lines, thresholds, growth and sprite packs live in
  `pet.json` (see `skills/lockdock/pet.md`).
- Modes live in one JSON file and the look in another (`theme.json`: position,
  scale, sections, autohide, icons, ...); an agent edits them. Every icon is an
  [Icona](https://icona.works/icons) line icon tinted with the palette; any of
  them (or an emoji) can be swapped in theme.json `icons` or a mode's `icon`. See `AGENTS.md` and
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
lockdock agents           # running coding agents and whether they need you
lockdock agents install-hooks --dry-run   # show the hook changes, then run without --dry-run
lockdock agent focus <id> # focus an agent's window
lockdock pet              # the pet's mood; also: calm, mood <m>|auto, mute, unmute,
                          #   pack <name>, packs, say "<text>"
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
    prompts.py        PromptCenter: site / notification / verdict decision cards
    state.py          state.json snapshot (+ agents / pet / theme sections)
    agents.py         AgentRegistry: agent kinds table, scan + hook merge, window walk
    agent_hooks.py    install-hooks merge for Claude Code settings.json / Codex config.toml
    pet.py            PetBrain: mood, growth and speech lines of the dock pet
    theme.py          ThemeConfig (validated theme.json) and ThemeService
    rules.py events.py
  adapters/           hyprland, dbus_notifications (busctl), claude_cli (+cache, pet speaker),
                      json_config, pet_packs, file_state, control_socket, shell_commands, clock,
                      proc_scan, http_url_source
  features/           optional features, auto-discovered (install(daemon)): agents, pet, browser_urls, prompts, theme
  cli/                main.py (verbs), agents.py (agent verbs), client.py (control socket client)
shell/                Quickshell dock (reads $XDG_RUNTIME_DIR/lockdock/state.json)
  Dock.qml            the panel window; builds the row from theme.sections (sectionMap)
  components/         Theme (st.theme helper), ModeStrip, AppStrip, AgentsPill + AgentsPanel
                      (or AgentStrip), HeldBadge, Nudge, PromptStack + PromptCard (decision cards),
                      ModePill, AppButton, Pet, PetSprite, PetOverlay (the grown pet, one per screen)
  components/Icon.qml one icon by name: icona:<slug>, a theme icon or a text glyph
  icons/icona/        Icona SVGs (MIT) + INDEX.md (slug -> name)
  pets/cat/           the built-in sprite pack (pack.json + SVG frames)
  pets/icona-cat/     a second pack, drawn from Icona's Black Cat
browser-extension/    WebExtension that reports the active tab URL to the daemon
tests/                pytest with fakes for every port
docs/architecture.md  ports, adapters, state.json sections, how to add a feature
skills/lockdock/      the Claude Code skill: pages for modes, theme, pet, agents, browser
modes.example.json    default modes; copied to ~/.config/lockdock/modes.json
pet.example.json      default pet config; copied to ~/.config/lockdock/pet.json
theme.example.json    default theme; copied to ~/.config/lockdock/theme.json
skills/lockdock/      agent skill: SKILL.md index + modes.md, theme.md, ...
```

Tests: `uv run --no-project --python 3.14 --with pytest pytest -q`

## Credits

Icons: [Icona](https://icona.works/icons) by Komal Verma
([github.com/komalverma22/Icona](https://github.com/komalverma22/Icona)), MIT; the
licence is in `shell/icons/icona/LICENSE`. The `icona-cat` pet is drawn from its Black Cat.

## Known limits

- A held notification is closed right after the daemon receives it, so the
  notification daemon may flash it for a frame. Owning the Notifications bus
  name ourselves would fix that but would replace your notification daemon.
- Window focus comes from Hyprland's event socket, so this does not work on
  other compositors yet (the dock itself is compositor-agnostic Quickshell).
