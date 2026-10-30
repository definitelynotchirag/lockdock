# Dock icons (theme.json `icons`)

The dock's icons are [Icona](https://icona.works/icons) line icons (MIT), shipped as SVGs in
`shell/icons/icona/` and tinted with the palette. An icon value is any of:
`"icona:<slug>"` (a file `shell/icons/icona/<slug>.svg`), `"brand:<slug>"` (an agent's logo from
`shell/icons/brand/`: `claude`, `openai`, `gemini`, `copilot`, `opencode`), a text glyph or
emoji (`"☕"`), a freedesktop icon name (`"firefox"`, `"com.t3tools.T3Code"`), or `""` for no icon.

| key | default | where |
|---|---|---|
| `icons.pack` | `"icona"` | `"text"`: every icon key you do not set falls back to the old text glyphs (●, ◆, 🔕, 🔔, 🌐, ✦, ✅) |
| `icons.stroke` | 1.75 | Icona line width on the 24 px grid (0.5 - 3; Icona's own is 1.5, thin at 16 px) |
| `icons.mode_fallback` | `icona:target` | a mode without an `icon` in modes.json |
| `icons.agents` | `icona:sketch-robot` | the agents pill (always this robot; the list shows each agent's own logo); a kind with no icon |
| `icons.agent_kinds` | claude `brand:claude`, codex `brand:openai`, gemini `brand:gemini`, opencode `brand:opencode`, t3 `com.t3tools.T3Code` (the app icon), aider `icona:git-branch`, cursor-agent `icona:cursor` | kind -> icon in the agents list; merges over the defaults. Wins over the kind's `glyph` in modes.json unless that glyph is itself `icona:...` / `brand:...` |
| `icons.held` / `icons.held_muted` | `icona:bell` / `icona:snooze` | held badge; `held_muted` while the active mode's `notifications.default` is `"hold"` |
| `icons.timer` / `icons.stay` | `icona:hourglass` / `icona:target` | countdown pill / Stay pill (`timer: ""` shows the target mode's icon) |
| `icons.nudge` | `icona:alert` | the off-task bubble |
| `icons.tag_urgent` / `tag_info` / `tag_ok` | `icona:alert` / `icona:info` / `icona:check-circle` | decision-card tag by level |
| `icons.card_notification` / `card_site` / `card_verdict` | `icona:bell` / `icona:compass` / `icona:check-circle` | a card whose app has no desktop icon |
| `icons.app_fallback` | `icona:layers` | an app in the strip with no desktop icon |
| `icons.pin` / `icons.pin_off` | `icona:map-pin-fill` / `icona:map-pin` | the pin button (section `"pin"`): pinned / not pinned (`motion.md`) |
| `icons.close` | `icona:x` | the close button on a window preview card (`motion.md`) |

**Picking a slug.** `shell/icons/icona/INDEX.md` lists every slug with its name and style
(596: outline, `-fill` and `-color` variants, pixel art `pixel-*`, doodles `doodle-*`). Grep it
(`grep -i rocket shell/icons/icona/INDEX.md`), prefer the plain outline slug (it takes the palette
colour; `-color` variants keep their own colours), and check the file exists before setting it:
`ls "$(lockdock skill path)/../../shell/icons/icona/rocket.svg"` (the repo is two levels above the
skill). A slug that does not exist draws a small dot and the shell logs `unknown icon`. The
validator only checks the form (`icona:` + lowercase words joined by `-`).

## Recipes

- "A rocket for Claude": `lockdock theme set icons.agent_kinds.claude '"icona:rocket"'`; "a different held icon": `theme set icons.held '"icona:inbox-zero"'`
- "Bolder icons": `lockdock theme set icons.stroke 2`; "the old emoji / glyph look": `theme set icons.pack '"text"'`
- "No icon on the Stay pill": `lockdock theme set icons.stay '""'`

Check the result with a screenshot (`grim`) before telling the user it is done.
