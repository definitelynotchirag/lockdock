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
| `palette` | `"system"` | where colours come from: `"system"` follows the desktop's Material You `colors.json` (see below), `"dark"` / `"light"` force a built-in palette, or an object of role overrides merged over a base: `{"base": "system", "accent": "#e5484d"}` (`base` defaults to `"system"`) |
| `layout` | `"islands"` | `"islands"`: each section group is its own floating rounded island (the pet shares the modes island); `"slab"`: one card with hairline dividers |
| `position` | `"bottom"` | `"bottom"` or `"top"` |
| `margin` | 10 | px from the screen edge (not scaled) |
| `scale` | 1.0 | multiplies every size (0.3 - 4) |
| `radius` | 20 | island / card corner radius |
| `gap` | 8 | px between islands |
| `fill_opacity` | 1.0 | island fill alpha (below 1 lets window text show through on this compositor setup) |
| `background` | `null` | legacy: a fixed island/card fill (`#AARRGGBB`, `#RRGGBB` or `rgba(r,g,b,a)`; r,g,b 0-1, or 0-255 if any is above 1; a 0-1). `null` = palette `bg` |
| `border` | `{color: null, width: 1, off_task_color: null}` | outline; `null` colours = palette `outline` / `danger` |
| `shadow` | `{enabled: true, opacity: 0.28}` | soft drop shadow under each island |
| `accent_override` | `null` | colour instead of each mode's colour (and the palette accent) |
| `font` | `{family: "Inter Display", size: 14}` | `""` or a family that is not installed = system font |
| `icon_size` | 34 | app icon px; buttons, pills and islands grow with it |
| `sections` | `["pet","modes","apps","agents","held"]` | what is shown, in order; unknown ids are ignored, missing ids are hidden |
| `show_unpinned` | true | dimmed icons for running apps not pinned to the mode |
| `autohide` | `{enabled: false, reveal_px: 4, hide_delay_ms: 600}` | slides away when idle; hover the screen edge to reveal. Stays up during a countdown, a nudge, or held notifications |
| `nudge` | `{enabled: true}` | the "off task" bubble (palette `danger`) |
| `agents` | `{style: "pill", max_rows: 8}` | agent inbox: `"pill"` = one pill (count, red dot + "N need you" when an agent waits) that opens a list, `max_rows` rows (1-50) before it scrolls; `"chips"` = one chip per agent. See `agents.md` |
| `opacity` | 1.0 | whole dock |

## Palette (colours)

The dock draws only with palette roles: `bg`, `bg_elevated`, `surface`, `surface_hover`, `text`, `text_muted`, `outline`, `accent`, `on_accent`, `accent_container`, `on_accent_container`, `secondary`, `tertiary`, `danger`, `on_danger`, `success`, `warning`, `bubble`, `bubble_text`, `shadow`. With `palette: "system"` they are mapped from the first existing of `~/.config/lockdock/colors.json` (your own drop-in) and `~/.local/state/quickshell/user/generated/colors.json` (end-4 / matugen, regenerated with the wallpaper), both flat `{material_role: "#rrggbb"}` dicts: `bg` = surface_container, `surface` = surface_container_highest, `text` = on_surface, `text_muted` = on_surface_variant, `outline` = outline_variant, `accent` = primary, `accent_container` = primary_container, `danger` = error, `bubble` = inverse_surface. The file is watched: a new wallpaper or a light/dark switch recolours the dock within a few seconds. Without the file the built-in dark or light palette is used, chosen by `gsettings get org.gnome.desktop.interface color-scheme` (dark if gsettings is unavailable). `lockdock theme` prints the resolved roles and where they came from.

Legacy colour keys win over the palette when set (`background`, `border.color`, `border.off_task_color`, `accent_override`). A theme.json written before palettes existed (no `palette` or `layout` key) keeps only the values that differ from the old defaults; the seeded old dark card colours, radius 22, icon size 36 and the empty font are dropped. The next `theme set` writes the file in the new form.

Mode colours: in modes.json `"color": "auto"` (the default) gives the active mode pill the palette's `accent_container` with an `accent` dot; an explicit `"#rrggbb"` still fills the pill with that colour.

## Recipes

- "Move the dock to the top": `lockdock theme set position '"top"'`
- "Make it smaller": `lockdock theme set scale 0.8` (bigger icons only: `icon_size`)
- "Hide the held badge": `lockdock theme set sections '["pet","modes","apps","agents"]'`
- "Only show apps, then modes": `lockdock theme set sections '["apps","modes"]'`
- "Autohide": `lockdock theme set autohide.enabled true`
- "Force dark (or light) colours": `lockdock theme set palette '"dark"'`; back to the wallpaper: `'"system"'`
- "Use my red as the accent but keep the wallpaper colours": `lockdock theme set palette '{"accent": "#e5484d", "accent_container": "#5c1a1d", "on_accent_container": "#ffdad8"}'` (set the whole object; a role is not a dotted key)
- "The old single-card look": `lockdock theme set layout '"slab"'`
- "Glassier islands": `lockdock theme set fill_opacity 0.9`; "no shadows": `theme set shadow.enabled false`
- "A fixed background colour": `theme set background '"#FF1C1C21"'` (`null` to follow the palette again)
- "No off-task bubble": `lockdock theme set nudge.enabled false`
- "One chip per agent again": `lockdock theme set agents.style '"chips"'` (back: `'"pill"'`)

Check the result with a screenshot (`grim`) before telling the user it is done.
