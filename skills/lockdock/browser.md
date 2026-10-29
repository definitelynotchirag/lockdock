# Browser URL rules (lockdock)

Hyprland only gives a browser's window title. The browser URL bridge (a WebExtension in
`browser-extension/` talking to the daemon on `127.0.0.1`) adds the active tab URL, so rules and
the LLM can judge `reddit.com/r/rust` differently from `reddit.com`.

## Writing URL rules

`on_task` / `off_task` regexes (case-insensitive) now match `class|title|url`. Off wins over on.
Edit `~/.config/lockdock/modes.json`; it hot-reloads within 2 s.

```json
"on_task":  ["docs\\.rs|crates\\.io", "github\\.com"],
"off_task": ["reddit\\.com(?!/r/rust)", "youtube\\.com/(?!watch\\?v=.*rust)"]
```

- Remember JSON needs `\\.` for a regex `\.`.
- Anchor on the host (`reddit\\.com`) so a page title containing "reddit" does not match by accident.
- Without the extension the URL part is empty, so URL-only rules never match; keep a title
  fallback (`"reddit"`) if you must work without it.

## Checking it works

```
lockdock url          # bridge: listening on 127.0.0.1:47231 / connected: yes / url: ...
lockdock status       # activity line; state.json activity.url is set when a browser is focused
lockdock log -n 20    # verdict reason names the matching rule
```

`connected: no` means no report in the last 10 minutes: the extension is not installed, the
port/token differ, or no browser window was focused. `NOT listening` means the port is taken.

## Enable / disable / configure

Top-level key in modes.json (changes need a daemon restart, unlike rules):

```json
"browser_bridge": { "enabled": true, "port": 47231, "token": "" }
```

Set `enabled: false` to stop the listener. Use a `token` if other local users share the machine;
put the same value in the extension options page.

## Installing the extension

See `browser-extension/README.md`. Chromium/Helium: `helium://extensions` or
`chrome://extensions`, Developer mode, Load unpacked `browser-extension/`. Firefox:
`about:debugging`, Load Temporary Add-on, pick `manifest.json`. Set the port in the options
page if it is not 47231.
