#!/usr/bin/env bash
# Demo helpers for recording lockdock. Usage:
#   scripts/demo.sh prep      make the pet quick-tempered and held notifications short-lived (backs up configs)
#   scripts/demo.sh notify [app] [summary] [body]   send a desktop notification (held or passed by the mode)
#   scripts/demo.sh agent [kind] [state]            pretend a coding agent changed state (claude needs_input)
#   scripts/demo.sh restore   put pet.json / modes.json back
set -euo pipefail
CFG=${XDG_CONFIG_HOME:-$HOME/.config}/lockdock
case "${1:-}" in
  prep)
    cp -n "$CFG/pet.json" "$CFG/pet.json.predemo" 2>/dev/null || true
    cp -n "$CFG/modes.json" "$CFG/modes.json.predemo" 2>/dev/null || true
    lockdock pet set thresholds.suspicious 8
    lockdock pet set thresholds.annoyed 16
    lockdock pet set thresholds.furious 25
    lockdock pet set grow_s 20
    lockdock pet set nag_every_s 15
    lockdock held timeout 1
    lockdock dnd off
    lockdock pet calm
    echo "demo config on: cat suspicious 8 s, annoyed 16 s, furious 25 s, full size 20 s later; held released after 1 min"
    ;;
  notify)
    app=${2:-Slack}; summary=${3:-"Priya: can you look at the deploy?"}; body=${4:-"#infra is waiting on you"}
    gdbus call --session --dest org.freedesktop.Notifications --object-path /org/freedesktop/Notifications \
      --method org.freedesktop.Notifications.Notify "$app" 0 "" "$summary" "$body" '[]' '{}' 8000 >/dev/null
    echo "sent: $app / $summary"
    ;;
  agent)
    lockdock agent-event "${2:-claude}" "${3:-needs_input}" '{"message": "Should I rewrite the migration or keep both tables?"}'
    echo "agent event: ${2:-claude} ${3:-needs_input}"
    ;;
  restore)
    [ -f "$CFG/pet.json.predemo" ] && mv "$CFG/pet.json.predemo" "$CFG/pet.json"
    [ -f "$CFG/modes.json.predemo" ] && mv "$CFG/modes.json.predemo" "$CFG/modes.json"
    lockdock pet calm; lockdock dnd off
    echo "restored"
    ;;
  *) sed -n 2,6p "$0"; exit 1 ;;
esac
