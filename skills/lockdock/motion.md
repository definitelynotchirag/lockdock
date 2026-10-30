# Pinning, tooltips and motion

Four theme.json keys (`lockdock theme set <key> <json>`); all hot-reload.

## `pinned` (default `false`)

Pinned, the dock reserves its row like the macOS dock with autohide off: maximised and tiled windows stop at the island row plus `margin` instead of sliding under it. The reserved size is the islands only (not the transparent room above them for cards, bubbles and tooltips) and follows `scale`, `icon_size`, `margin` and `position` (top or bottom edge). Unpinned (the default) the dock is an overlay that windows cover. A pinned dock never autohides, even with `autohide.enabled: true`.

```
lockdock pin            # pin (same as `pin on`)
lockdock unpin          # back to an overlay (same as `pin off`)
lockdock pin toggle     # flip; the dock's pin button sends this
```

The quick settings gear (section `"settings"`, in the default sections; see `theme.md`) has a Pin dock switch and shows an accent dot while pinned. A bare pin button is the optional section `"pin"`, not shown by default. Add it near the end of `sections` (it shares the island of its neighbour, like the pet):
`lockdock theme set sections '["pet","modes","apps","agents","held","pin","settings"]'`.
Pinned it shows `icons.pin` (filled map pin) on the accent container; unpinned `icons.pin_off` (outline). Swap either in `icons` (see `icons.md`).

Check it: `hyprctl -j monitors` lists `reserved` per monitor (`[left, top, right, bottom]`); pinning at the bottom adds the dock height (66 px at the default scale) to the last number.

## `tooltips` (default `{enabled: true, delay_ms: 350}`)

The dock draws its own tooltips (an island-style bubble with an icon, a bold title and a muted detail) above the hovered item, or below it when the dock is at the top. `delay_ms` (0-5000) is the hover time before the first tip; moving to the next item while one shows switches at once. A click hides the tip until the pointer leaves. `enabled: false` turns them all off.

## `previews` (default `{enabled: true, delay_ms: 350, width: 200, height: 120, max: 6}`)

Hovering a running app for `delay_ms` opens a panel of live window thumbnails above it (below it at the top), one card per window: the live picture fitted into `width` x `height` px, the window title (bold for the focused one) and the app icon. Click a card to focus that window; the x in its corner (`icons.close`) closes it. More than `max` windows shows "+N more". The panel stays open while the pointer is on the app or the panel and closes 250 ms after it leaves both; moving to another running app switches at once. It fades and slides in over 140 ms, out over 100 ms (instant with `reduced_motion`). A running app shows previews instead of its tooltip; `enabled: false` brings the tooltip back. Thumbnails need the compositor's toplevel capture (Hyprland has it); a window that cannot be captured shows "no preview".

## `reduced_motion` (default `false`)

`true` makes every interaction animation instant: hover fades, press springs, tooltips, window previews, the agents list opening, the slide of an autohiding dock. Status animations stay (the countdown fill, the pulsing "needs you" outline, the pet's speech bubble pop).

## The interaction language (what the user sees)

Hover fades a `surface_hover` background in behind a button or pill (180 ms in, 240 ms out); app icons get a soft rounded halo. Nothing moves on hover. A press shrinks the item to 0.96 and springs back on release. No colours here are configurable beyond the palette roles in `theme.md`.

## `popups` (default `{open_on_hover: true}`)

The agents list, a running app's window previews and the quick settings panel open after `tooltips.delay_ms` of hovering their pill and close 250 ms (the agents list: 700 ms) after the pointer has left the pill and the panel. `open_on_hover: false` makes every popup click-only: the agents pill and the gear toggle on click, a running app with several windows opens its previews on click (one window: the click focuses it) and the previews stay until a click on a card, the app or elsewhere; hover then shows plain tooltips again. The "Open panels on hover" switch in quick settings flips the same key.
