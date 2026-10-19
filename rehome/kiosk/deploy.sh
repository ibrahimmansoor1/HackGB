#!/bin/sh
# Build the kiosk page on this machine, copy the kiosk to the Pi, and restart it there.
# Usage: sh kiosk/deploy.sh [pi@hackpi.local]
set -e
PI=${1:-pi@hackpi.local}
cd "$(dirname "$0")"
(cd ui && npm install --no-audit --no-fund && npm run build)
tar -cz server.py ui/dist pi |
  ssh "$PI" 'mkdir -p ~/rehome-kiosk && rm -rf ~/rehome-kiosk/ui/dist && tar -xz -C ~/rehome-kiosk'
ssh "$PI" 'if systemctl --user is-enabled --quiet rehome-kiosk 2>/dev/null; then
  systemctl --user restart rehome-kiosk && echo "Restarted; the kiosk page reloads by itself."
else
  echo "Copied. First time on this Pi? Run: sh ~/rehome-kiosk/pi/setup.sh"
fi'
