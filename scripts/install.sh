#!/usr/bin/env bash
# Link the CLI into ~/.local/bin and install user systemd units.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p ~/.local/bin ~/.config/systemd/user ~/.config/lockdock
ln -sf "$ROOT/bin/lockdock" ~/.local/bin/lockdock
[ -f ~/.config/lockdock/modes.json ] || cp "$ROOT/modes.example.json" ~/.config/lockdock/modes.json
cp "$ROOT"/systemd/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now lockdock-daemon.service lockdock-shell.service
echo "lockdock installed. Modes: ~/.config/lockdock/modes.json   Status: lockdock status"
