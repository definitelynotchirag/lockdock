# lockdock

A dock for Hyprland with focus modes, a cat that scolds you, and an inbox of
the coding agents running on your machine. A Linux build of
[the macOS dock trq212 showed](https://x.com/trq212/status/2115135857669881939),
with a few things added.

## What it does

**Modes.** You define modes in a JSON file (Writing, Building, Free, anything).
Each mode has its own apps, its own on-task and off-task rules, and its own
notification policy. The dock shows the active mode, the other modes as small
buttons, and the mode's apps. Running apps that are not part of the mode sit
after a divider.

**Leaving costs time.** Switching out of a mode starts a countdown. Each extra
press makes it shorter, so you can still leave, but not by reflex. A Stay
button cancels the switch.

**It knows what you are doing.** The daemon watches the focused window (and the
active browser tab, through a small extension) and judges it against the mode.
Rules run first. Anything the rules do not cover goes to a classifier: the
hosted [Jev](https://typesafe.ai) decision model, or `claude -p` through your
Claude Code login. An off-task window turns the dock red with a one-line reason
such as "x.com is off task in Writing".

**The cat.** A pixel cat lives in the dock. It is content while you work, then
suspicious, annoyed and furious the longer you stay off task, and says so in a
speech bubble. Past furious it grows into a click-through overlay until it
covers most of the screen. Go back to the task and it shrinks in four seconds.
Click it to calm it. Everything about it lives in `pet.json`: the lines, the
timings, the sprite pack, or `enabled: false` for no cat at all.

**Notifications.** A notification that does not belong to the mode is held:
closed as it arrives, re-delivered when the mode ends or after 15 minutes
(configurable, 0 for never). Keywords like "urgent" and critical urgency pass
through. Do not disturb holds everything silently, with no cards and no badge,
and re-delivers it when you turn it off.

**Decision cards.** When something needs a choice, a card floats above the
dock. A held message that looks time-sensitive gets Later and Go to Building.
A site that belongs to another mode gets Stay and Go to Social (30 s wait). A
fresh verdict on a site no mode knows shows as a toast that fades.

**Agent inbox.** One pill lists every coding agent running on the machine:
Claude Code, Codex, OpenCode, Aider, Gemini CLI, cursor-agent, T3 Code. Red and
pulsing when one is waiting for you, green while they work. Hover it for the
list, each row with the agent's own logo, and click a row to focus its window.
`lockdock agents install-hooks` wires Claude Code and Codex hooks so the state
is exact instead of guessed from the process tree.

**A normal dock too.** Hover a running app for live window previews. Pin the
dock so windows stop at it, or let it autohide. Quick settings behind the gear:
pin, autohide, top or bottom, tooltips, previews, hover-to-open, reduced motion,
do not disturb, the held time limit, and the cat's timings as steppers.

**An agent configures it.** Modes, theme and pet are three JSON files, and the
repo ships a Claude Code skill that knows them. "Add a Research mode with
Zotero and the browser, hold Slack" edits the config and the dock changes live.
The CLI covers the same ground for humans.

**Looks like your desktop.** The palette follows the wallpaper through the
Material You colors.json that end-4 and matugen write. Icons are
[Icona](https://icona.works/icons) line icons tinted with the palette, and any
of them can be swapped for another Icona slug, an emoji, or a theme icon.

## Requirements

- Hyprland (window focus comes from its event socket)
- [Quickshell](https://quickshell.org) 0.3 or newer
- Python 3.11 or newer, standard library only
- `busctl` from systemd, for watching notifications
- One of: a `TYPESAFE_API_KEY` in `~/.config/lockdock/.env` for Jev, the
  `claude` CLI logged in, or `llm.enabled: false` to run on rules alone

## Install

```
git clone <this repo> ~/Projects/lockdock
cd ~/Projects/lockdock
./scripts/install.sh      # links ~/.local/bin/lockdock, installs two user units, links the skill
lockdock status
```

The installer copies `modes.example.json`, `theme.example.json` and
`pet.example.json` to `~/.config/lockdock/` on first run and never overwrites
them. For the browser tab URL, load `browser-extension/` as an unpacked
extension; its README has the steps.

To run the pieces by hand instead of the units: `lockdock daemon` and
`lockdock shell`.

## Use

```
lockdock mode writing       # switch; press again during the countdown to shorten it
lockdock status             # mode, verdict for the current window, held count
lockdock log -n 50          # every verdict with its reason
lockdock classify helium "Home / X - Helium" --mode writing   # ask the classifier once

lockdock held               # held notifications; `release` re-delivers them now
lockdock held timeout 30    # re-deliver on their own after 30 min (0 = never)
lockdock dnd on|off|toggle  # do not disturb

lockdock agents             # running coding agents and whether they need you
lockdock agents install-hooks --dry-run

lockdock pet                # mood, size, last line; also calm, mute, on|off, pack, say, set
lockdock pet set thresholds.furious 120

lockdock theme              # the effective theme; `theme set <key> <json>`, `theme reset`
lockdock pin | unpin        # windows stop at the dock, or cover it again
lockdock skill path         # the Claude Code skill (also linked at ~/.claude/skills/lockdock)
```

`lockdock --help` lists every verb.

## Configuration

Three files in `~/.config/lockdock/`, all hot-reloaded:

| file | what | documented in |
|---|---|---|
| `modes.json` | modes, their apps and rules, notification policy, the classifier, agent kinds | `skills/lockdock/modes.md`, `agents.md`, `browser.md` |
| `theme.json` | position, scale, sections, autohide, palette, icons, tooltips, previews, popups, pinned | `skills/lockdock/theme.md`, `icons.md`, `motion.md` |
| `pet.json` | persona, lines, thresholds, growth, sprite pack, enabled | `skills/lockdock/pet.md` |

The skill pages are written for an agent but read fine for a person. Each has
a key table and a list of recipes.

## How it is built

A Python daemon and a Quickshell dock. The daemon is ports and adapters: the
core has no I/O, the adapters wrap Hyprland, busctl, the classifiers and the
JSON files, and features such as the pet, the agent inbox and the theme plug in
through `install(daemon)`. The daemon writes `state.json`; the dock watches that
file and draws. `docs/architecture.md` has the ports, the state sections and a
recipe for adding a feature.

```
lockdock/
  core/        models, daemon, modes, activity, notifications, prompts, agents, pet, theme, state
  adapters/    hyprland, dbus_notifications, claude_cli, jev, json_config, pet_packs, proc_scan, ...
  features/    agents, pet, theme, prompts, browser_urls, notifications, classify
  cli/         the lockdock command
shell/
  Dock.qml     the panel window; builds its row from theme.sections
  components/  ModeStrip, AppStrip, AgentsPill, AgentsPanel, HeldBadge, PromptStack, Pet,
               PetOverlay, WindowPreviews, QuickSettings, Tip, Pressable, Icon, ...
  icons/       icona/ (Icona SVGs) and brand/ (agent logos)
  pets/        sprite packs: cat, icona-cat
browser-extension/   reports the active tab URL to the daemon
skills/lockdock/     the Claude Code skill
tests/               pytest with fakes for every port
```

Tests:

```
uv run --no-project --python 3.14 --with pytest pytest -q
```

## Known limits

- A held notification is closed right after the daemon sees it, so the
  notification daemon may flash it for a frame. Owning the Notifications bus
  name would fix that, at the cost of replacing your notification daemon.
- Window focus comes from Hyprland's event socket. The dock itself is plain
  Quickshell, but the daemon does not know other compositors yet.
- Window previews need the compositor's toplevel capture. Hyprland has it.

## Credits

The idea and the interaction design are from
[trq212's macOS dock](https://x.com/trq212/status/2115135857669881939).
Icons are [Icona](https://icona.works/icons) by Komal Verma, MIT, licence in
`shell/icons/icona/LICENSE`. Agent logos come from
[Simple Icons](https://simpleicons.org), CC0, see `shell/icons/brand/LICENSE`.
The `icona-cat` pet is drawn from Icona's Black Cat.
