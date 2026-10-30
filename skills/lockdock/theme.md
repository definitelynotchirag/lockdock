# theme.json

`~/.config/lockdock/theme.json` (`lockdock theme path`; defaults in `theme.example.json`). Hot-reloaded. The dock reads nothing else for its look. A bad value falls back to its default and is logged as `theme_error` (`lockdock log`); `lockdock theme` prints the effective theme and lists problems.

```
lockdock theme                       # effective theme
lockdock theme set position '"top"'  # dotted key, JSON value (strings need quotes)
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
| `sections` | `["pet","modes","apps","agents","held","settings"]` | what is shown, in order; unknown ids are ignored, missing ids are hidden. `"settings"`: the quick settings gear (below); optional `"pin"`: a bare pin button (`motion.md`) |
| `show_unpinned` | true | dimmed icons for running apps not pinned to the mode |
| `autohide` | `{enabled: false, reveal_px: 4, hide_delay_ms: 600}` | slides away when idle; hover the screen edge to reveal. Stays up during a countdown, a nudge, or held notifications |
| `nudge` | `{enabled: true}` | the "off task" bubble (palette `danger`) |
| `agents` | `{style: "pill", max_rows: 8}` | agent inbox: `"pill"` = one pill (count, red dot + "N need you" when an agent waits) that opens a list, `max_rows` rows (1-50) before it scrolls; `"chips"` = one chip per agent. See `agents.md` |
| `prompts` | `{enabled: true, max_visible: 3, width: 360}` | decision cards above the dock (below it at the top): a held message that needs an answer, a site that belongs to another mode, a verdict toast for an unknown site. `max_visible` 1-10 (the newest win), `width` 200-1000 px before `scale` (toasts may be up to 1.45x wider). `enabled: false` hides them |
| `mode_strip` | `{stay_button: true}` | while a switch is pending the mode strip shows a timer pill (`icons.timer`, label, m:ss; click to shorten the wait) and a Stay pill that cancels; `false` drops the Stay pill |
| `pinned` | false | reserve the dock's row so windows stop at it (`lockdock pin` / `unpin` / `pin toggle`); never autohides. See `motion.md` |
| `tooltips` | `{enabled: true, delay_ms: 350}` | the dock's own tooltips; `delay_ms` 0-5000 before the first one. See `motion.md` |
| `previews` | `{enabled: true, delay_ms: 350, width: 200, height: 120, max: 6}` | live window thumbnails when hovering a running app (replace its tooltip): `delay_ms` 0-5000, each thumbnail fitted into `width` (80-800) x `height` (50-600) px before `scale`, at most `max` (1-20) cards then "+N more". `enabled: false` brings back the app tooltip. See `motion.md` |
| `reduced_motion` | false | hover, press, tooltip and slide animations become instant. See `motion.md` |
| `icons` | Icona set | every icon the dock draws that is not an app icon: see `icons.md` |
| `opacity` | 1.0 | whole dock |

**Quick settings.** The gear (section `"settings"`, `icons.settings`, an accent dot while pinned) opens a small panel on hover (after `tooltips.delay_ms`; it closes 250 ms after the pointer leaves the gear and the panel) or on click. One switch per row: Pin dock (`pin toggle`), Auto-hide (`autohide.enabled`, dimmed while pinned), Position: Top (`position`), Tooltips, Window previews (`tooltips` / `previews.enabled`), Show other running apps (`show_unpinned`), Reduce motion (`reduced_motion`), Mute the pet (`pet mute` / `unmute`, only with a pet); a footer opens theme.json. The rows show the live file, so a change made here or by an agent shows at once.

## Palette (colours)

The dock draws only with palette roles: `bg`, `bg_elevated`, `surface`, `surface_hover`, `text`, `text_muted`, `outline`, `accent`, `on_accent`, `accent_container`, `on_accent_container`, `secondary`, `tertiary`, `danger`, `on_danger`, `success`, `warning`, `bubble`, `bubble_text`, `shadow`. With `palette: "system"` they are mapped from the first existing of `~/.config/lockdock/colors.json` (your own drop-in) and `~/.local/state/quickshell/user/generated/colors.json` (end-4 / matugen, regenerated with the wallpaper), both flat `{material_role: "#rrggbb"}` dicts: `bg` = surface_container, `surface` = surface_container_highest, `text` = on_surface, `text_muted` = on_surface_variant, `outline` = outline_variant, `accent` = primary, `accent_container` = primary_container, `danger` = error, `bubble` = inverse_surface. The file is watched: a new wallpaper or a light/dark switch recolours the dock within a few seconds. Without the file the built-in dark or light palette is used, chosen by `gsettings get org.gnome.desktop.interface color-scheme` (dark if gsettings is unavailable). `lockdock theme` prints the resolved roles and where they came from.

Legacy colour keys win over the palette when set (`background`, `border.color`, `border.off_task_color`, `accent_override`). A theme.json written before palettes existed (no `palette` or `layout` key) keeps only the values that differ from the old defaults; the seeded old dark card colours, radius 22, icon size 36 and the empty font are dropped. The next `theme set` writes the file in the new form.

Mode colours: in modes.json `"color": "auto"` (the default) gives the active mode pill the palette's `accent_container` with an `accent` dot; an explicit `"#rrggbb"` still fills the pill with that colour.

## Recipes

- "Move the dock to the top": `lockdock theme set position '"top"'`; "autohide": `theme set autohide.enabled true`; "smaller": `theme set scale 0.8` (icons only: `icon_size`)
- "Windows should not cover the dock": `lockdock pin`; "a pin button": the quick settings gear has a Pin switch, a bare button is section `"pin"` (`motion.md`); "no gear": drop `"settings"` from `sections`; "no tooltips": `theme set tooltips.enabled false`; "no window previews": `theme set previews.enabled false`; "bigger previews": `theme set previews.width 280` and `previews.height 170`
- "Hide the held badge": `lockdock theme set sections '["pet","modes","apps","agents"]'`; "only apps, then modes": `'["apps","modes"]'`
- "Force dark (or light) colours": `lockdock theme set palette '"dark"'`; back to the wallpaper: `'"system"'`. "Use my red as the accent but keep the wallpaper colours": `lockdock theme set palette '{"accent": "#e5484d", "accent_container": "#5c1a1d", "on_accent_container": "#ffdad8"}'` (set the whole object; a role is not a dotted key)
- "The old single-card look": `lockdock theme set layout '"slab"'`; "glassier islands": `theme set fill_opacity 0.9`; "no shadows": `theme set shadow.enabled false`; "a fixed background": `theme set background '"#FF1C1C21"'` (`null`: palette). "No off-task bubble": `lockdock theme set nudge.enabled false`; "no Stay button during a countdown": `theme set mode_strip.stay_button false`; "no cards above the dock": `theme set prompts.enabled false`; "one card at a time": `theme set prompts.max_visible 1`; "wider cards": `theme set prompts.width 420`; "one chip per agent again": `theme set agents.style '"chips"'` (back: `'"pill"'`)

Check the result with a screenshot (`grim`) before telling the user it is done.
