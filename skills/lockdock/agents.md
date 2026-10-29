# lockdock agent inbox

The dock shows one pill for all running coding agents: a glyph, the count and
a dot. When an agent waits for you the dot turns red, the pill says "2 need
you" and its outline pulses (it never opens by itself). Click the pill for the
list: one row per agent (waiting first, then working, idle, done) with its
glyph, label (project dir), last message, age and dot; the cwd is in the row's
tooltip. Click a row to focus that agent's window. The list closes on a second
click on the pill, on a row click, or 0.7 s after the pointer leaves it.

theme.json `agents`: `max_rows` (default 8) rows show before the list scrolls;
`style: "chips"` brings back one chip per agent in the dock
(`lockdock theme set agents.style '"chips"'`, back with `'"pill"'`).

| state | dot | meaning |
|---|---|---|
| `needs_input` | red, pulsing | waiting for the user: permission prompt, question, turn finished (Codex) |
| `working` | green | busy (hook said so, or the process is using CPU) |
| `idle` | grey | running, quiet, no hook has reported anything |
| `done` | grey | turn or session finished; an exited agent stays 10 min |

`needs_input` sends one notification ("<kind> needs you · <label>") that modes never hold;
it clears on the next working/done event or when the user focuses the agent's window.

## Read the current agents

```
lockdock agents            # ID KIND STATE AGE LABEL WINDOW MESSAGE/CWD (--json: state.json form)
lockdock agent focus <id>  # id, unique id prefix, or label
lockdock log -n 50         # "kind": "agent" lines record every state change
```

`WINDOW -`: no Hyprland window found (e.g. tmux). Stuck on `idle`: no hooks.

## Install hooks (exact state instead of a CPU guess)

```
lockdock agents install-hooks --dry-run    # print the diff, change nothing
lockdock agents install-hooks              # both; or --claude / --codex
```

- Claude Code: appends `lockdock agent-event claude <state>` entries to
  `~/.claude/settings.json` hooks (Notification -> needs_input,
  UserPromptSubmit / PreToolUse -> working, Stop / SessionEnd -> done).
  Existing hooks are kept; re-running adds nothing; the first run backs the
  file up to `settings.json.bak-lockdock`.
- Codex: adds top-level `notify = ["lockdock", "agent-event", "codex", "needs_input"]`
  to `~/.codex/config.toml` unless a `notify` is already set (Codex allows one).
- Other agents: call `lockdock agent-event <kind> <state>` from their hook or
  notify setting, with the event JSON on stdin or as the last argument
  (`session_id`/`cwd`/`message` are read). It is silent and always exits 0.

## Add or change an agent kind

Top-level `agents.kinds` in `~/.config/lockdock/modes.json` merges over the
built-in table (t3, claude, codex, opencode, aider, gemini, cursor-agent):

```json
"agents": { "kinds": [ { "name": "goose", "glyph": "🪿", "patterns": ["goose"], "exclude": ["run"] },
                       { "name": "aider", "enabled": false }, { "name": "claude", "glyph": "C" } ] }
```

`patterns`: regexes full-matched (case-insensitive) on the program name
(basename of argv[0], or of the script a node/python/bun interpreter runs); a
pattern with `/` is searched in the full path. `exclude`: arguments that
disqualify a process (`-p` one-shots). `ancestors`: a program that must be an
ancestor (how T3 Code children become `t3`). `label_arg`: flag whose value
names the chip. `hook_kind`: the kind its hook events use. New names go
before the built-ins; the first match wins. Reloads within 2 s.
