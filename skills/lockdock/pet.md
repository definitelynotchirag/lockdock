# Customising the lockdock pet

A pixel cat lives in the dock. It follows the activity verdicts: content on task,
then suspicious, annoyed and furious the longer you stay off task. When furious it
grows into a click-through overlay until you go back to the task. Click it to calm it.

Everything lives in `~/.config/lockdock/pet.json` (seeded from `pet.example.json`,
hot-reloaded within 2 s; a JSON error logs `pet_config_error` and keeps the old
config). Check the result with `lockdock pet` (mood, scale, seconds off task, line).

Timings have a verb that validates, writes pet.json and applies live:
`lockdock pet set <key> <number>` with `thresholds.suspicious|annoyed|furious`, `grow_s`,
`shrink_s`, `decay_per_s`, `nag_every_s` (seconds) or `max_scale` (sprites). It rejects values
below the bounds in the table and thresholds out of order (suspicious <= annoyed <= furious).
The user can do the same from the dock: the quick settings gear has a **Pet** group with
steppers for Suspicious / Annoyed / Furious after, Grows to full in and Nags every
(`st.pet.config` in state.json holds the effective timings).

## Keys

| key | default | meaning |
|---|---|---|
| `persona` | grey cat, dramatic | one sentence; the voice for LLM lines |
| `lines.<mood>` | 5 each | lines per mood: `content`, `suspicious`, `annoyed`, `furious` |
| `thresholds` | `{suspicious: 45, annoyed: 120, furious: 300}` | seconds off task for each mood (0 or more, in order) |
| `decay_per_s` | 2.0 | off-task seconds forgiven per second on task (0 or more) |
| `grow_s` / `shrink_s` | 240 / 4 | seconds of furious to reach full size / to shrink back (at least 1 / 0.1) |
| `max_scale` | 24 | full size in dock sprites (48 px x 24; at least 1) |
| `max_screen_fraction` | 0.9 | the overlay never gets taller than this share of the screen |
| `nag_every_s` | 60 | a fresh line this often while off task (never while content; at least 5) |
| `llm_lines` | false | on a mood change, ask `claude -p` for a line in the persona's voice |
| `muted` | false | keep the mood, drop lines and growth |
| `enabled` | true | `false`: no pet at all (no sprite, bubble, growth or overlay); `lockdock pet off` / `pet on`, or the "Show the pet" switch in quick settings |
| `pack`, `position`, `name` | `cat`, `left`, `""` | sprite pack, `left`/`right` of the mode strip, display name |

Lines are templates: `{app}`, `{mode}` (mode label), `{reason}` (why the verdict
was off) and `{title}` (window title, 60 chars). Unknown `{fields}` stay as written.
Tease the activity, never the person.

## Recipes

- **Angrier faster:** lower `thresholds` (e.g. `{"suspicious": 20, "annoyed": 60, "furious": 120}`)
  and `grow_s` (e.g. `lockdock pet set grow_s 90`). Slower forgiveness: `pet set decay_per_s 1`.
- **Gentler:** raise the thresholds, set `max_screen_fraction` to 0.4, or `lockdock pet mute`.
- **New voice:** change `persona`, rewrite `lines`, optionally `"llm_lines": true`. LLM
  lines are cached per (mood, app) in `~/.local/state/lockdock/pet-lines-cache.json`;
  delete it after changing the persona.
- **Preview:** `lockdock pet mood furious` (jumps to full size), `lockdock pet mood annoyed`,
  then `lockdock pet mood auto`. `lockdock pet say "hello"` shows a line now.
- **Reset:** `lockdock pet calm` (or click the pet). `lockdock pet mute` / `unmute` persist to pet.json.

## Making a sprite pack

Put it in `~/.config/lockdock/pets/<name>/` (a user pack with the same name as a
built-in one wins), then `lockdock pet pack <name>`. `lockdock pet packs` lists them.
`shell/pets/cat/` is the built-in example. A second built-in pack, `icona-cat` (Nori, a
black line-art cat drawn from Icona's Black Cat icon), is one command away:
`lockdock pet pack icona-cat` (back: `lockdock pet pack cat`). `pack.json`:

```json
{"name": "Miso", "author": "you", "size": 48,
 "moods": {"content":    {"frames": ["content-1.svg", "content-2.svg"], "fps": 2},
           "suspicious": {"frames": ["suspicious-1.svg"], "fps": 1},
           "annoyed":    {"frames": ["annoyed-1.svg", "annoyed-2.svg"], "fps": 4},
           "furious":    {"frames": ["furious-1.svg", "furious-2.svg"], "fps": 6}}}
```

Frames are paths relative to the pack dir (SVG or PNG), square, `size` px nominal. All
four moods should exist; a missing mood shows nothing. They are scaled without smoothing,
so pixel art stays crisp; a vector pack sets `"pixel": false` in pack.json to be drawn
smoothed at its real size instead (icona-cat does). Frames can repeat in the list to hold a pose longer. If a pack
is missing or its pack.json is invalid, the daemon falls back to `cat`.
