# Pinning, tooltips and motion

Three theme.json keys (`lockdock theme set <key> <json>`); all hot-reload.

## `pinned` (default `false`)

Pinned, the dock reserves its row like the macOS dock with autohide off: maximised and tiled windows stop at the island row plus `margin` instead of sliding under it. The reserved size is the islands only (not the transparent room above them for cards, bubbles and tooltips) and follows `scale`, `icon_size`, `margin` and `position` (top or bottom edge). Unpinned (the default) the dock is an overlay that windows cover. A pinned dock never autohides, even with `autohide.enabled: true`.

```
lockdock pin            # pin (same as `pin on`)
lockdock unpin          # back to an overlay (same as `pin off`)
lockdock pin toggle     # flip; the dock's pin button sends this
```

The pin button is an optional dock section, `"pin"`, not shown by default. Add it to the end of `sections` (it shares the island of its neighbour, like the pet):
`lockdock theme set sections '["pet","modes","apps","agents","held","pin"]'`.
Pinned it shows `icons.pin` (filled map pin) on the accent container; unpinned `icons.pin_off` (outline). Swap either in `icons` (see `icons.md`).

Check it: `hyprctl -j monitors` lists `reserved` per monitor (`[left, top, right, bottom]`); pinning at the bottom adds the dock height (66 px at the default scale) to the last number.

## `tooltips` (default `{enabled: true, delay_ms: 350}`)

The dock draws its own tooltips (an island-style bubble with an icon, a bold title and a muted detail) above the hovered item, or below it when the dock is at the top. `delay_ms` (0-5000) is the hover time before the first tip; moving to the next item while one shows switches at once. A click hides the tip until the pointer leaves. `enabled: false` turns them all off.

## `reduced_motion` (default `false`)

`true` makes every interaction animation instant: hover fades, the icon lift, press springs, tooltips, the agents list opening, the slide of an autohiding dock. Status animations stay (the countdown fill, the pulsing "needs you" outline, the pet's speech bubble pop).

## The interaction language (what the user sees)

Hover fades a `surface_hover` background in behind a button or pill (180 ms in, 240 ms out) and lifts its icon 1.5 px; app icons lift 2 px over a soft rounded halo, and dimmed running apps brighten. A press shrinks the item to 0.96 and springs back on release. No colours here are configurable beyond the palette roles in `theme.md`.
