# modes.json

`~/.config/lockdock/modes.json` (schema and defaults in `modes.example.json` in the repo; `lockdock config` prints the path). The daemon hot-reloads it within 2 s. Per mode:

| key | meaning |
|---|---|
| `id`, `label`, `icon`, `color` | identity; `icon` is a text glyph (emoji / unicode); `color` is `"auto"` (default: the palette accent, see `theme.md`) or `"#rrggbb"` |
| `description` | one or two sentences; **this is the prompt the classifier sees**, write it like a brief |
| `apps` | desktop-entry ids shown in the dock for this mode (`ls /usr/share/applications`) |
| `on_task` / `off_task` | regexes (case-insensitive) matched against `class\|title`; off wins |
| `unknown` | `ask` (LLM decides), `neutral`, or `off` for anything no rule matches |
| `off_task_action` | `nudge` (dock turns red with the reason), `notify`, or `none` |
| `notifications.allow_from` / `hold_from` | regexes on `appName\|desktop-entry` |
| `notifications.pass_keywords` | regexes on summary+body that always pass |
| `notifications.default` | `pass`, `hold`, or `ask` (LLM decides) |
| `exit_delay_s`, `per_press_s` | exit countdown when leaving this mode; each extra press cuts the wait |
| `on_enter` / `on_exit` | shell commands (e.g. `hyprctl dispatch workspace 2`) |

Top level: `default_mode`, `dwell_s` (how long a window must stay focused before it is judged), `llm.enabled`, `llm.model` (a `claude -p` model alias), `browsers` (classes judged by tab title, never by being a mode app).

## How to find out what went wrong

```
lockdock log -n 50        # events.jsonl: every verdict with its reason
lockdock status           # current mode, verdict, held count
lockdock held             # what is being held right now
```

A line like `"verdict": "off", "reason": "matches off_task rule 'docs'"` tells you exactly which rule to loosen. Verdicts from the LLM are cached in `~/.local/state/lockdock/classify-cache.json`; delete a key there if you changed a description and want it re-judged (or run `lockdock reclassify`).

## Rules of thumb

- Prefer a regex over a description change: rules are free and instant, the LLM costs a call per new window title.
- Browsers are judged by title only. A site the mode needs goes in `on_task`.
- Critical-urgency notifications always pass; do not try to hold them.
- Keep `lockdock status` green after an edit: a JSON error logs `config_error` and the previous config stays active.

## Examples

- "Add a Research mode": copy a mode object, give it a new `id`, `label`, `icon`, `color` (`"auto"` unless they want a colour), a `description` that says what research means for this user, `apps`, and `on_task` regexes for the sites they use.
- "Stop flagging the Rust book as off task": add `"rust-lang\\.org|doc\\.rust"` to the active mode's `on_task` (and remove the matching `off_task` rule if one exists, since off wins).
- "Let Linear notifications through in Building": add `"Linear"` to that mode's `notifications.allow_from`.
