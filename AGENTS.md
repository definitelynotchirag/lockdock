# lockdock — notes for agents

lockdock is a mode-aware dock for Hyprland. **You are the agent that tunes it.**
The user asks you things like "add a Research mode", "stop flagging the Rust
book as off task", "let Linear notifications through in Building". Do that by
editing the config and reading the log; never by patching the daemon for a
one-off rule.

## The surface you edit

`~/.config/lockdock/modes.json` (schema in `modes.example.json`). The daemon
hot-reloads it within 2 s. Per mode:

| key | meaning |
|---|---|
| `id`, `label`, `icon`, `color` | identity; `icon` is a text glyph (emoji / unicode) |
| `description` | one or two sentences; **this is the prompt the classifier sees**, write it like a brief |
| `apps` | desktop-entry ids shown in the dock for this mode (`ls /usr/share/applications`) |
| `on_task` / `off_task` | regexes (case-insensitive) matched against `class\|title\|url`; off wins |
| `unknown` | `ask` (LLM decides), `neutral`, or `off` for anything no rule matches |
| `off_task_action` | `nudge` (dock turns red with the reason), `notify`, or `none` |
| `notifications.allow_from` / `hold_from` | regexes on `appName\|desktop-entry` |
| `notifications.pass_keywords` | regexes on summary+body that always pass |
| `notifications.default` | `pass`, `hold`, or `ask` (LLM decides) |
| `exit_delay_s`, `per_press_s` | exit countdown when leaving this mode; each extra press cuts the wait |
| `on_enter` / `on_exit` | shell commands (e.g. `hyprctl dispatch workspace 2`) |

Top level: `default_mode`, `dwell_s` (how long a window must stay focused
before it is judged), `llm.enabled`, `llm.model` (a `claude -p` model alias),
`browsers` (classes judged by tab title, never by being a mode app),
`agents.kinds` (extra / overridden coding-agent kinds for the agent inbox;
see `skills/lockdock/agents.md`).

## How to find out what went wrong

```
lockdock log -n 50        # events.jsonl: every verdict with its reason
lockdock status           # current mode, verdict, held count
lockdock held             # what is being held right now
```

A line like `"verdict": "off", "reason": "matches off_task rule 'docs'"`
tells you exactly which rule to loosen. Verdicts from the LLM are cached in
`~/.local/state/lockdock/classify-cache.json`; delete a key there if you
changed a description and want it re-judged.

## Rules of thumb

- Prefer a regex over a description change: rules are free and instant,
  the LLM costs a call per new window title.
- Browsers are judged by title, plus the tab URL when the browser extension is installed (`skills/lockdock/browser.md`). A site the mode needs goes in `on_task`.
- Critical-urgency notifications always pass; do not try to hold them.
- Keep `lockdock status` green after an edit: a JSON error logs
  `config_error` and the previous config stays active.

## Changing the code (not the config)

Only when the user asks for a new capability. The daemon is ports and
adapters: read `docs/architecture.md` first. Core logic lives in
`lockdock/core/` (no subprocesses, no adapter imports), I/O in
`lockdock/adapters/`, new features as a module in `lockdock/features/`, dock
UI in `shell/components/`. Run the tests with
`uv run --no-project --python 3.14 --with pytest pytest -q`.
