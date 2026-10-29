# theme.json

`~/.config/lockdock/theme.json` (`lockdock theme path`; defaults in `theme.example.json`). Hot-reloaded. The dock reads nothing else for its look. A bad value falls back to its default and is logged as `theme_error` (`lockdock log`); `lockdock theme` prints the effective theme and lists problems.

```
lockdock theme                       # effective theme
lockdock theme set margin 24         # dotted key, JSON value (strings need quotes)
lockdock theme set position '"top"'
lockdock theme reset                 # back to the defaults
```

`theme set` validates first: a wrong key or value is rejected and nothing is written.

| key | default | meaning |
|---|---|---|
| `position` | `"bottom"` | `"bottom"` or `"top"` |
| `margin` | 10 | px from the screen edge (not scaled) |
| `scale` | 1.0 | multiplies every size (0.3 - 4) |
| `radius` | 22 | card corner radius |
| `background` | `rgba(0.11,0.11,0.13,0.86)` | `#AARRGGBB`, `#RRGGBB` or `rgba(r,g,b,a)` (r,g,b 0-1, or 0-255 if any is above 1; a 0-1) |
| `border` | `{color, width: 1, off_task_color}` | card outline; `off_task_color` while off task |
| `accent_override` | `null` | colour instead of each mode's colour |
| `font` | `{family: "", size: 14}` | `""` = system font |
| `icon_size` | 36 | app icon px; buttons and pills grow with it |
| `sections` | `["pet","modes","apps","agents","held"]` | what is shown, in order; unknown ids are ignored, missing ids are hidden |
| `show_unpinned` | true | dimmed icons for running apps not pinned to the mode |
| `autohide` | `{enabled: false, reveal_px: 4, hide_delay_ms: 600}` | slides away when idle; hover the screen edge to reveal. Stays up during a countdown, a nudge, or held notifications |
| `nudge` | `{enabled: true}` | the red "off task" bubble |
| `opacity` | 1.0 | whole dock |

## Recipes

- "Move the dock to the top": `lockdock theme set position '"top"'`
- "Make it smaller": `lockdock theme set scale 0.8` (bigger icons only: `icon_size`)
- "Hide the held badge": `lockdock theme set sections '["pet","modes","apps","agents"]'`
- "Only show apps, then modes": `lockdock theme set sections '["apps","modes"]'`
- "Autohide": `lockdock theme set autohide.enabled true`
- "Make it opaque with a red accent": `theme set background '"#FF1C1C21"'`, `theme set accent_override '"#e5484d"'`
- "No red bubble": `lockdock theme set nudge.enabled false`

Check the result with a screenshot (`grim`) before telling the user it is done.
