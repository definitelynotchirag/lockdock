---
name: lockdock
description: Tune and debug lockdock, the mode-aware Hyprland dock. Use when the user mentions "lockdock", "my dock", "the dock", "focus mode", "the cat" (the dock pet), asks to "add a mode", change how the dock looks (position, size, autohide, sections), says "the dock is flagging X" or "stop flagging X as off task", asks which notifications are held, or wants agents or the browser tab connected to the dock. You edit config files and read the log through the `lockdock` CLI; you do not patch the daemon for a one-off rule.
---

# lockdock

- lockdock is a dock for Hyprland with focus **modes** (Writing, Building, ...). A Python daemon watches the focused window and judges it against the active mode (rules first, then a classifier for unknowns: `claude -p`, or Jev with `llm.provider: "jev"`); a Quickshell dock renders the result.
- Off-task windows turn the dock red with a reason; notifications that do not fit the mode are held and re-delivered when the mode ends.
- You are the agent that tunes it: change behaviour by editing a config file, never by patching code for a single rule.
- Every config file is hot-reloaded (modes.json within 2 s). A JSON error keeps the previous config active and logs an error.
- Code changes (new features) are a different job: see `AGENTS.md` and `docs/architecture.md` in the repo (`lockdock skill path` prints this skill's directory; the repo is two levels up).

## Config files and their CLI verbs

| file | what it controls | CLI | page |
|---|---|---|---|
| `~/.config/lockdock/modes.json` | modes, rules, notification policy, held time limit, do not disturb, LLM (`llm.provider`) | `lockdock config` (path), `modes`, `mode <id>`, `reload`, `classify <class> "<title>" [--mode <id>]`, `held`, `held timeout <min>`, `release`, `dnd on\|off\|toggle` | `modes.md` |
| `~/.config/lockdock/theme.json` | every visual knob of the dock | `lockdock theme`, `theme set <key> <json>`, `theme reset`, `theme path`, `pin` / `unpin` / `pin toggle` | `theme.md`, `motion.md` |
| `~/.config/lockdock/pet.json` | the dock pet: persona, lines, thresholds, growth, sprite pack | `lockdock pet`, `pet calm`, `pet mood <m>\|auto`, `pet mute\|unmute`, `pet pack <name>`, `pet packs`, `pet say "<text>"`, `pet set <key> <number>` | `pet.md` |
| `modes.json` → `agents.kinds` | coding agents shown in the dock (Claude Code, Codex, OpenCode, Aider, Gemini, T3) | `lockdock agents`, `agents install-hooks [--dry-run]`, `agent focus <id>` | `agents.md` |

Browser tab URLs reach the dock through the extension in `browser-extension/` and `modes.json` → `browser_bridge`; `lockdock url` shows the bridge state: `browser.md`.

Prefer the CLI verbs over hand-editing when one exists (`theme set` validates and rejects bad values; a hand edit that is wrong falls back to defaults and is logged).

## Verification loop

After every change:

1. `lockdock status` - mode, verdict for the current window, held count. It must not error.
2. `lockdock log -n 30` - recent events. Look for `config_error` / `theme_error` (your edit was rejected) and for the `reason` on each verdict.
3. For visual changes, look at the dock (a screenshot) before telling the user it is done.

## Pages

- `modes.md` - modes.json keys, rules of thumb, debugging a wrong verdict
- `theme.md` - theme.json keys and recipes
- `motion.md` - pinning the dock (`lockdock pin`, the `"pin"` section), tooltips, reduced motion
- `icons.md` - the dock's icons (theme.json `icons`): Icona slugs, emoji, picking a slug from INDEX.md
- `pet.md` - the dock pet
- `agents.md` - agents in the dock
- `browser.md` - browser tab integration
