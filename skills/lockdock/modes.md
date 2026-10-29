# modes.json

`~/.config/lockdock/modes.json` (schema and defaults in `modes.example.json` in the repo; `lockdock config` prints the path). The daemon hot-reloads it within 2 s. Per mode:

| key | meaning |
|---|---|
| `id`, `label`, `icon`, `color` | identity; `icon` is `"icona:<slug>"` (an Icona line icon tinted with the palette, slugs in `shell/icons/icona/INDEX.md`, see `icons.md`) or a text glyph / emoji (`"☕"`); none = theme `icons.mode_fallback`; `color` is `"auto"` (default: the palette accent, see `theme.md`) or `"#rrggbb"` |
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

Top level: `default_mode`, `dwell_s` (how long a window must stay focused before it is judged), `llm.enabled`, `llm.model` (a `claude -p` model alias), `browsers` (classes judged by tab title, never by being a mode app), `prompts` (decision cards, below).

## Decision cards

Top level `"prompts": {"enabled": true, "site_cards": true, "notification_cards": true, "verdict_toasts": true, "stay_snooze_s": 600}` (all defaults). The dock shows at most 3 cards:

- **site**: the window is off task in this mode but another mode's `on_task` or `apps` claims it (first in modes.json order; catch-all modes like Free with `.*` never claim). "x.com · belongs to Social" with [Stay] [Go to Social (Ns wait)]; N is this mode's `exit_delay_s`. One card per host (or window class) per `stay_snooze_s`; resets on a mode switch. To make a card appear for a site, put it in the other mode's `on_task`.
- **notification**: every held notification. "held for X" when another mode's `notifications.allow_from` or `apps` matches the app (then a [Go to X] button), else "held in <mode>". A "Time-sensitive" tag comes from the classifier (only with `llm.enabled`). [Later] dismisses the card; the notification stays held.
- **verdict**: a toast for a fresh (uncached) LLM verdict on something no mode's rules know; fades after 6 s. Turn off with `verdict_toasts: false`.

`lockdock prompts` lists open cards; `lockdock prompt <id> later|dismiss|stay|switch` presses a button. Every card is logged as `"kind": "prompt"` in `lockdock log`. A mode switch clears all cards.

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

- "Add a Research mode": copy a mode object, give it a new `id`, `label`, `icon` (e.g. `"icona:search"`; check the slug in INDEX.md), `color` (`"auto"` unless they want a colour), a `description` that says what research means for this user, `apps`, and `on_task` regexes for the sites they use.
- "Stop flagging the Rust book as off task": add `"rust-lang\\.org|doc\\.rust"` to the active mode's `on_task` (and remove the matching `off_task` rule if one exists, since off wins).
- "Let Linear notifications through in Building": add `"Linear"` to that mode's `notifications.allow_from`.
