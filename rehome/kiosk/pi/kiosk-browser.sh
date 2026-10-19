#!/bin/sh
# Opens the kiosk page full screen in Chromium. pi/setup.sh starts it from the labwc
# autostart through lwrespawn, which restarts it if it exits.
URL=${KIOSK_URL:-http://localhost:8080/}

# server.py starts at boot too; wait for it so Chromium doesn't open on an error page
for _ in $(seq 1 90); do
  curl -fs -o /dev/null "$URL" && break
  sleep 1
done

exec chromium --kiosk --ozone-platform=wayland --noerrdialogs --disable-infobars --no-first-run \
  --password-store=basic --disable-session-crashed-bubble --disable-features=Translate \
  --autoplay-policy=no-user-gesture-required --check-for-update-interval=31536000 \
  --overscroll-history-navigation=0 --disable-pinch \
  --user-data-dir="$HOME/.config/rehome-kiosk-browser" "$URL"
