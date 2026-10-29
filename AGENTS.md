# lockdock - notes for agents

lockdock is a mode-aware dock for Hyprland. **You are the agent that tunes it.**
The user asks you things like "add a Research mode", "stop flagging the Rust
book as off task", "move the dock to the top". Do that by editing the config
and reading the log, never by patching the daemon for a one-off rule.

**Start with the skill:** `skills/lockdock/SKILL.md` (`lockdock skill path`
prints its directory). It indexes the config files and their CLI verbs, the
verification loop, and one page per feature (`modes.md`, `theme.md`, ...). The
modes.json key table and rules of thumb live in `skills/lockdock/modes.md`.
`scripts/install.sh` links the skill into `~/.claude/skills/lockdock`.

## Changing the code (not the config)

Only when the user asks for a new capability. The daemon is ports and
adapters: read `docs/architecture.md` first (it has the "How to add a feature"
recipe). Core logic lives in `lockdock/core/` (no subprocesses, no adapter
imports), I/O in `lockdock/adapters/`, new features as a module in
`lockdock/features/`, dock UI in `shell/components/` (placed through
`theme.sections` in `shell/Dock.qml`). Everything visual is configurable in
`theme.json`: new UI must read its sizes, fonts and colours from
`shell/components/Theme.qml`. A feature that changes how an agent configures
the dock also updates its page in `skills/lockdock/`. Run the tests with
`uv run --no-project --python 3.14 --with pytest pytest -q`.
