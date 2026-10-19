#!/bin/sh
# One-time Pi setup, run on the Pi as pi:  sh ~/rehome-kiosk/pi/setup.sh
# Starts server.py at boot (systemd user service) and opens the kiosk page full screen
# when the desktop logs in (labwc autostart). Undo with:  sh ~/rehome-kiosk/pi/setup.sh --remove
set -e
DIR=$(cd "$(dirname "$0")/.." && pwd)
AUTOSTART=$HOME/.config/labwc/autostart
UNIT=$HOME/.config/systemd/user/rehome-kiosk.service

if [ "$1" = "--remove" ]; then
  systemctl --user disable --now rehome-kiosk 2>/dev/null || true
  rm -f "$UNIT"
  systemctl --user daemon-reload
  [ -f "$AUTOSTART" ] && sed -i "\#$DIR/pi/kiosk-browser.sh#d" "$AUTOSTART"
  echo "Removed. Lingering is still on; turn it off with: sudo loginctl disable-linger $USER"
  exit 0
fi

[ -f "$DIR/kiosk.env" ] || cp "$DIR/pi/kiosk.env.example" "$DIR/kiosk.env"
mkdir -p "$(dirname "$UNIT")" "$(dirname "$AUTOSTART")"
cp "$DIR/pi/rehome-kiosk.service" "$UNIT"
[ -e "/var/lib/systemd/linger/$USER" ] || sudo loginctl enable-linger "$USER"  # start user services at boot
systemctl --user daemon-reload
systemctl --user enable --now rehome-kiosk
grep -qF "$DIR/pi/kiosk-browser.sh" "$AUTOSTART" 2>/dev/null ||
  echo "/usr/bin/lwrespawn $DIR/pi/kiosk-browser.sh &" >> "$AUTOSTART"
echo "Done. Set REHOME_BACKEND in $DIR/kiosk.env, then: systemctl --user restart rehome-kiosk"
