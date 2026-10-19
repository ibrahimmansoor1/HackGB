# ReHome kiosk

A Raspberry Pi donation station, built as an extra for HackGB 2026 (it won Best Hardware). Walk up, hold something to the camera, press the button. The kiosk photographs it, the parser agent reads it (tags included), and the person chooses:

- **Press:** donate it. It becomes searchable right away.
- **Hold:** sell it instead. The pricing agent quotes a price range; press again and the kiosk shows it as listed, with a coin burst. Posting to the marketplace isn't wired up yet, so nothing is listed for real.

Nothing is saved until they choose. The screen streams the agents' steps from `/api/events` while they work. Pressing the button three times quickly goes back to the start screen from anywhere.

## Hardware

Raspberry Pi 4 with a Grove Base Hat, a USB webcam and a screen (it ran on a 480x800 portrait panel; landscape screens and projectors get a side-by-side layout). A Pi 5 should work too: gpiozero's lgpio backend supports it, but that's untested.

| Part | Where | Used for |
|---|---|---|
| Button | D26 (GPIO26) | the only control: press, or hold for 1.2 s |
| LED | D5 (GPIO5) | breathes while idle, steady when someone is there ("press me") |
| LED | D16 (GPIO16) | countdown ticks, errors |
| Webcam | USB (Logitech Brio 101) | the photo, the live viewfinder, the ASCII mirror, and presence: motion in the picture wakes the kiosk |

The space bar and tapping the screen also work as the button.

## How it fits together

```
Chromium (kiosk mode) ──> server.py on the Pi ──/api/*──> ReHome backend
                           │ camera, button, LEDs
                           └ serves ui/dist
```

`server.py` is the only process that touches the GPIO pins and the camera. It serves the kiosk page and forwards `/api/*` and `/static/*` to the backend, so the page needs no CORS and the backend URL lives in one setting. It needs Python 3 with numpy, Pillow and gpiozero, plus ffmpeg. All of these come with Raspberry Pi OS.

| Route | |
|---|---|
| `GET /hw/events` | Server-sent events: `state` on connect, then `button`, `presence`, `camera`, `leds` |
| `GET /hw/stream.mjpg?fps=12`, `GET /hw/frame.jpg` | Live camera, current frame |
| `POST /hw/leds` | `{"pattern": "idle" \| "ready" \| "tick" \| "flash" \| "thinking" \| "success" \| "error" \| "off", "then": …}` |
| `POST /hw/button` | `{"pressed": true}`: a virtual press, for testing without the hardware |
| `GET /config.json` | `zip`, `site`, `backend` |

The page (`ui/`, Svelte 5 + Tailwind) calls the backend only from `ui/src/lib/api.js`: `POST /api/items/parse`, then `/{draft_id}/donate` or `/{draft_id}/sell`.

## Try it on a laptop

```sh
cd kiosk/ui && npm install && npm run build && cd ..
python3 server.py --fake --backend http://localhost:8000    # test pattern instead of a webcam
python3 server.py --fake --camera /dev/video0 --backend …   # or a real webcam (Linux)
```

Open http://localhost:8080 and press space. For UI work, run `KIOSK_SERVER=http://localhost:8080 npm run dev` in `ui/` for hot reload.

## Set up the Pi

From the repo, on a machine with Node:

```sh
sh kiosk/deploy.sh                 # builds the page, copies it to pi@hackpi.local:~/rehome-kiosk
```

Then once, on the Pi:

```sh
sh ~/rehome-kiosk/pi/setup.sh      # server at boot + Chromium kiosk on login
nano ~/rehome-kiosk/kiosk.env      # REHOME_BACKEND = the backend as the Pi sees it
systemctl --user restart rehome-kiosk
```

After that, `deploy.sh` restarts the server and the open kiosk page reloads by itself. `setup.sh --remove` undoes the setup. Logs: `journalctl --user -u rehome-kiosk -f`.

If the backend runs on a laptop on the same Wi-Fi, start uvicorn with `--host 0.0.0.0` and set `REHOME_BACKEND=http://<laptop ip>:8000`. If the backend only listens on localhost, or a firewall blocks the Pi, forward it over SSH from the laptop instead, and leave `REHOME_BACKEND` at its default:

```sh
ssh -N -R 8000:127.0.0.1:8000 pi@hackpi.local   # the Pi's localhost:8000 is now the laptop's backend
```
