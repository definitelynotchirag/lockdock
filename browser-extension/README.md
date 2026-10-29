# lockdock URL bridge

A Manifest V3 WebExtension that reports the active tab URL to the lockdock daemon
(`POST http://127.0.0.1:47231/url`), so rules can tell `reddit.com/r/rust` from `reddit.com`.
Works unmodified in Chromium-based browsers (Helium, Chrome, Brave, Edge) and Firefox.

## Install

Chromium-based (Helium: `helium://extensions`, others: `chrome://extensions`):
1. Enable Developer mode.
2. Load unpacked, select this `browser-extension/` directory.

Firefox: open `about:debugging#/runtime/this-firefox`, "Load Temporary Add-on...", pick
`browser-extension/manifest.json` (temporary until restart; permanent installs need signing).

## Configure

Open the extension's options page. Port defaults to 47231 and must match `browser_bridge.port`
in `~/.config/lockdock/modes.json`. The optional token is sent as `Authorization: Bearer <token>`
and must match `browser_bridge.token`. Check with `lockdock url`.
