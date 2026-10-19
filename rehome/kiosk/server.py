#!/usr/bin/env python3
"""ReHome kiosk server for the Raspberry Pi.

One process owns the kiosk hardware and serves the kiosk page:
  D5   LED      GPIO5    "press me"
  D16  LED      GPIO16   countdown ticks, errors
  D26  button   GPIO26   the Grove module pulls it low; pressed = high
  USB  webcam   its MJPEG frames are passed through ffmpeg untouched (about 1% CPU)

The page only talks to this server:
  /                   the built kiosk page (ui/dist)
  /hw/...             camera, button and LEDs
  /api/*, /static/*   forwarded to the ReHome backend, so the page needs no CORS
                      and the backend URL is set in one place (--backend)

Usage:
  python3 server.py --backend http://<laptop>.local:8000 [--port 8080] [--zip 54311]
  python3 server.py --fake [--camera /dev/video0]    # no GPIO, e.g. on a laptop
Only clients on local networks may connect unless --open is given.
"""

import argparse
import glob
import io
import ipaddress
import json
import math
import os
import queue
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parent
UI = BASE / "ui" / "dist"
BOOT = f"{time.time():.0f}"  # changes on every restart, so open kiosk pages know to reload


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def log(kind, msg):
    print(f"[{kind}] {msg}", flush=True)


# ----------------------------------------------------------------------------- events

class Hub:
    """Fans hardware events out to every open /hw/events stream."""

    def __init__(self):
        self.lock = threading.Lock()
        self.clients = set()

    def subscribe(self):
        q = queue.Queue(maxsize=200)
        with self.lock:
            self.clients.add(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            self.clients.discard(q)

    def publish(self, kind, data):
        with self.lock:
            for q in self.clients:
                try:
                    q.put_nowait((kind, data))
                except queue.Full:
                    pass  # a stalled client misses events instead of blocking the hardware threads


hub = Hub()

# ----------------------------------------------------------------------------- LEDs


def breathe(t, period):
    return 0.5 - 0.5 * math.cos(2 * math.pi * t / period)


def idle(t):
    return 0.06 + 0.6 * breathe(t, 5), 0


def tick(t):
    return 0, 1 if t < 0.15 else max(0.0, 1 - (t - 0.15) / 0.35)


def flash(t):
    level = 1 if t < 0.3 else max(0.0, 1 - (t - 0.3) / 0.4)
    return level, level


def thinking(t):
    return breathe(t, 1.6), breathe(t + 0.8, 1.6)


def success(t):
    if t < 1.5:  # three quick double blinks, then a slow fade
        on = 1 if (t * 4) % 1 < 0.6 else 0
        return on, on
    level = 0.5 + 0.5 * math.cos(math.pi * min(1.0, (t - 1.5) / 2.5))
    return level, level


def error(t):
    return 0, 1 if (t * 5) % 1 < 0.5 else 0


# name: (levels at t seconds -> (d5, d16), length in seconds or None, pattern that follows)
PATTERNS = {
    "off": (lambda t: (0, 0), None, None),
    "idle": (idle, None, None),
    "ready": (lambda t: (1, 0), None, None),
    "tick": (tick, 0.5, "off"),
    "flash": (flash, 0.7, "off"),
    "thinking": (thinking, None, None),
    "success": (success, 4.0, "idle"),
    "error": (error, 1.6, "off"),
}


class Leds:
    """Both LEDs follow one named pattern, computed from the clock at 50 Hz so fades stay smooth."""

    def __init__(self, fake):
        self.pins = None
        if not fake:
            from gpiozero import PWMLED
            self.pins = (PWMLED(5), PWMLED(16))
        self.lock = threading.Lock()
        self.name, self.then, self.t0 = "off", None, time.monotonic()
        self.levels = (0.0, 0.0)
        threading.Thread(target=self._loop, daemon=True).start()

    def set(self, name, then=None):
        if name not in PATTERNS or (then is not None and then not in PATTERNS):
            raise ApiError(400, f"pattern must be one of {', '.join(PATTERNS)}")
        with self.lock:
            self.name, self.then, self.t0 = name, then, time.monotonic()
        hub.publish("leds", {"pattern": name})

    def close(self):
        if self.pins:
            for pin in self.pins:
                pin.close()

    def _loop(self):
        while True:
            advanced = None
            with self.lock:
                fn, length, follow = PATTERNS[self.name]
                t = time.monotonic() - self.t0
                if length is not None and t >= length:
                    advanced = self.then or follow or "off"
                    self.name, self.then, self.t0 = advanced, None, time.monotonic()
                    fn, t = PATTERNS[advanced][0], 0.0
            if advanced:
                hub.publish("leds", {"pattern": advanced})
            levels = tuple(min(1.0, max(0.0, float(v))) for v in fn(t))
            if levels != self.levels:
                self.levels = levels
                if self.pins:
                    for pin, level in zip(self.pins, levels):
                        pin.value = level * level  # rough gamma, so fades look even to the eye
            time.sleep(0.02)


# ----------------------------------------------------------------------------- button

class ButtonInput:
    """The Grove button, plus a virtual one (POST /hw/button) for testing without the hardware."""

    def __init__(self, fake):
        self.lock = threading.Lock()
        self.pressed, self.presses, self._down_at = False, 0, None
        self.button = None
        if not fake:
            from gpiozero import Button
            self.button = Button(26, pull_up=False, bounce_time=0.01)
            self.button.when_pressed = lambda: self.change(True, "button")
            self.button.when_released = lambda: self.change(False, "button")

    def change(self, pressed, source):
        with self.lock:
            if pressed == self.pressed:
                return
            now = time.monotonic()
            self.pressed = pressed
            if pressed:
                self.presses += 1
                self._down_at = now
                data = {"pressed": True, "n": self.presses, "source": source}
            else:
                held = round((now - self._down_at) * 1000) if self._down_at else 0
                data = {"pressed": False, "n": self.presses, "held_ms": held, "source": source}
        hub.publish("button", data)
        if not pressed:
            log("button", f"press #{data['n']} held {data['held_ms']} ms ({source})")

    def close(self):
        if self.button:
            self.button.close()


# ----------------------------------------------------------------------------- camera

PRESENCE_HOLD = 4.0  # seconds without motion before nobody counts as present


class Camera:
    """Keeps the newest JPEG from the webcam, and turns motion in the picture into a presence signal."""

    def __init__(self, device, size, fps, threshold):
        self.device_arg, self.size, self.fps, self.threshold = device, size, fps, threshold
        self.cond = threading.Condition()
        self.frame, self.seq, self.frame_t = None, 0, 0.0
        self.status, self.device = "starting", None
        self.motion, self.present, self.last_motion = 0.0, False, None
        self._proc = None
        self._running = True
        target = self._fake_loop if device == "test" else self._capture_loop
        threading.Thread(target=target, daemon=True).start()
        threading.Thread(target=self._analyze_loop, daemon=True).start()

    def latest(self):
        return self.frame if self.status == "running" else None

    def wait_frame(self, after_seq, timeout):
        with self.cond:
            self.cond.wait_for(lambda: self.seq != after_seq, timeout)
            return self.frame, self.seq

    def stop(self):
        self._running = False
        if self._proc:
            self._proc.terminate()

    def _set_status(self, status):
        if status != self.status:
            self.status = status
            log("camera", status + (f" ({self.device})" if self.device and status == "running" else ""))
            hub.publish("camera", {"status": status, "device": self.device})

    def _find_device(self):
        if self.device_arg:
            return self.device_arg if os.path.exists(self.device_arg) else None
        found = sorted(glob.glob("/dev/v4l/by-id/usb-*-video-index0"))
        return found[0] if found else None

    def _capture_loop(self):
        while self._running:
            path = self._find_device()
            if not path:
                self._set_status("no camera")
                time.sleep(3)
                continue
            node = os.path.basename(os.path.realpath(path))
            try:
                self.device = Path(f"/sys/class/video4linux/{node}/name").read_text().strip()
            except OSError:
                self.device = node
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "v4l2", "-input_format", "mjpeg",
                   "-video_size", self.size, "-framerate", str(self.fps), "-i", path,
                   "-c:v", "copy", "-bsf:v", "mjpeg2jpeg", "-f", "image2pipe", "pipe:1"]
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            buf = b""
            while self._running:
                chunk = self._proc.stdout.read1(65536)
                if not chunk:
                    break
                buf += chunk
                while True:  # split the stream into JPEGs on the start/end-of-image markers
                    start = buf.find(b"\xff\xd8")
                    if start < 0:
                        buf = buf[-1:]
                        break
                    end = buf.find(b"\xff\xd9", start + 2)
                    if end < 0:
                        buf = buf[start:]
                        break
                    self._publish(buf[start:end + 2])
                    buf = buf[end + 2:]
            self._proc.kill()
            self._proc.wait()
            if self._running:
                self._set_status("restarting")
                time.sleep(2)

    def _fake_loop(self):
        """A warm test pattern with a drifting blob, for running without a webcam."""
        self.device = "test pattern"
        w, h = (int(v) for v in self.size.split("x"))
        y, x = np.mgrid[0:h, 0:w]
        glow = np.exp(-(((x - w * 0.5) / (w * 0.6)) ** 2 + ((y - h * 0.4) / (h * 0.7)) ** 2))
        base = np.stack([40 + 140 * glow, 28 + 90 * glow, 44 + 40 * glow], axis=-1).astype(np.uint8)
        background = Image.fromarray(base)
        t0 = time.monotonic()
        while self._running:
            t = time.monotonic() - t0
            img = background.copy()
            draw = ImageDraw.Draw(img)
            cx, cy, r = w * (0.5 + 0.25 * math.sin(t / 3)), h * (0.5 + 0.15 * math.sin(t / 2.1)), h * 0.18
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(242, 169, 59))
            draw.rectangle((w * 0.12, h * 0.62, w * 0.3, h * 0.9), fill=(220, 194, 154))
            out = io.BytesIO()
            img.save(out, "JPEG", quality=80)
            self._publish(out.getvalue())
            time.sleep(1 / self.fps)

    def _publish(self, jpeg):
        with self.cond:
            self.frame, self.seq, self.frame_t = jpeg, self.seq + 1, time.monotonic()
            self.cond.notify_all()
        if self.status != "running":
            self._set_status("running")

    def _analyze_loop(self):
        prev, last_seq = None, -1
        while self._running:
            time.sleep(0.2)
            now = time.monotonic()
            frame, seq = self.frame, self.seq
            if frame is None or seq == last_seq:
                if now - self.frame_t > 3:
                    prev = None
                    self._set_presence(now, 0.0)
                continue
            last_seq = seq
            try:
                img = Image.open(io.BytesIO(frame))
                img.draft("L", (160, 90))  # let libjpeg decode at 1/8 scale: a few ms per frame
                gray = np.asarray(img.convert("L").resize((160, 90)), dtype=np.float32)
            except Exception:
                continue
            if prev is not None:
                # ignore whole-image brightness shifts from auto exposure, count pixels that really changed
                diff = np.abs((gray - gray.mean()) - (prev - prev.mean()))
                self._set_presence(now, round(float((diff > 25).mean() * 100), 2))
            prev = gray

    def _set_presence(self, now, motion):
        self.motion = motion
        if motion >= self.threshold:
            self.last_motion = now
        present = self.last_motion is not None and now - self.last_motion < PRESENCE_HOLD
        if present != self.present:
            self.present = present
            log("presence", f"{'someone is here' if present else 'nobody'} (motion {motion}%)")
            hub.publish("presence", {"present": present, "motion": motion})


# ----------------------------------------------------------------------------- HTTP

def hw_state():
    return {
        "button": {"pressed": button.pressed, "n": button.presses},
        "presence": {"present": camera.present, "motion": camera.motion},
        "camera": {"status": camera.status, "device": camera.device},
        "leds": {"pattern": leds.name},
        "boot": BOOT,
    }


def client_is_local(host):
    try:
        ip = ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_loopback or ip.is_link_local or ip.is_private


CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".woff2": "font/woff2",
                 ".woff": "font/woff", ".png": "image/png", ".jpg": "image/jpeg", ".json": "application/json"}

NOT_BUILT = b"""<!doctype html><meta charset=utf-8><title>ReHome kiosk</title>
<body style="background:#1d1522;color:#f6e8d4;font:20px system-ui;display:grid;place-items:center;height:100vh;margin:0">
<p>The kiosk page isn't built yet. Run <code>npm install &amp;&amp; npm run build</code> in <code>kiosk/ui</code>.</p>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "ReHomeKiosk/1.0"

    def log_message(self, *args):
        pass

    def _allowed(self):
        if ARGS.open or client_is_local(self.client_address[0]):
            return True
        self.send_error(403, "Only devices on a local network may connect")
        return False

    def _send(self, body, ctype, status=200, cache="no-store"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status=200):
        self._send(json.dumps(obj).encode(), "application/json", status)

    def do_GET(self):
        if not self._allowed():
            return
        url = urlparse(self.path)
        path = url.path
        try:
            if path == "/hw/events":
                return self._sse()
            if path == "/hw/stream.mjpg":
                return self._mjpeg(parse_qs(url.query))
            if path == "/hw/frame.jpg":
                frame = camera.latest()
                return self._send(frame, "image/jpeg") if frame else self._json({"detail": "no camera"}, 503)
            if path == "/hw/state":
                return self._json(hw_state())
            if path == "/config.json":
                return self._json({"zip": ARGS.zip, "site": ARGS.site, "backend": ARGS.backend, "fake": ARGS.fake})
            if path.startswith(("/api/", "/static/")):
                return self._proxy("GET")
            self._static(path)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if not self._allowed():
            return
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/"):
                return self._proxy("POST")
            # Requiring JSON makes browsers preflight cross-site requests, so other pages can't drive the hardware
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._json({"detail": "send a JSON body with Content-Type: application/json"}, 415)
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self._json({"detail": "body must be a JSON object"}, 400)
            if path == "/hw/leds":
                leds.set(body.get("pattern"), body.get("then"))
                return self._json({"pattern": leds.name})
            if path == "/hw/button":
                button.change(bool(body.get("pressed")), "virtual")
                return self._json({"pressed": button.pressed})
            self._json({"detail": "not found"}, 404)
        except ApiError as e:
            self._json({"detail": str(e)}, e.status)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _proxy(self, method):
        """Forward a request to the ReHome backend and relay its answer as is."""
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if method == "POST" else None
        headers = {k: self.headers[k] for k in ("Content-Type", "Accept") if self.headers.get(k)}
        req = urllib.request.Request(ARGS.backend + self.path, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                return self._send(res.read(), res.headers.get("Content-Type", "application/octet-stream"), res.status)
        except urllib.error.HTTPError as e:
            return self._send(e.read(), e.headers.get("Content-Type", "application/json"), e.code)
        except (urllib.error.URLError, OSError) as e:
            reason = getattr(e, "reason", e)
            log("backend", f"{method} {self.path} failed: {reason}")
            return self._json({"detail": f"Can't reach the ReHome backend at {ARGS.backend} ({reason})"}, 502)

    def _static(self, path):
        root = UI.resolve()
        if not (root / "index.html").is_file():
            return self._send(NOT_BUILT, "text/html; charset=utf-8", 503)
        target = (root / path.lstrip("/")).resolve()
        if path == "/" or not target.is_relative_to(root) or not target.is_file():
            target = root / "index.html"
        # Vite puts a content hash in every asset name, so those can be cached for good
        cache = "public, max-age=31536000, immutable" if path.startswith("/assets/") else "no-store"
        ctype = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        self._send(target.read_bytes(), ctype, cache=cache)

    def _event(self, kind, data):
        self.wfile.write(f"event: {kind}\ndata: {json.dumps(data)}\n\n".encode())
        self.wfile.flush()

    def _sse(self):
        """Server-sent events: the hardware state on connect, then every button, presence, camera and LED change."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        q = hub.subscribe()
        try:
            self._event("state", hw_state())
            while True:
                try:
                    self._event(*q.get(timeout=15))
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")  # notices closed connections
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            hub.unsubscribe(q)

    def _mjpeg(self, query):
        try:
            fps = min(30.0, max(0.2, float(query.get("fps", ["12"])[0])))
        except ValueError:
            fps = 12.0
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        seq, idle_count = -1, 0
        try:
            while True:
                started = time.monotonic()
                frame, new_seq = camera.wait_frame(seq, timeout=5)
                if frame is None:
                    return
                if new_seq == seq:
                    # camera stalled: resend the last frame (which also notices a closed connection)
                    idle_count += 1
                    if idle_count > 12:
                        return
                else:
                    idle_count, seq = 0, new_seq
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                 + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n")
                time.sleep(max(0.0, 1 / fps - (time.monotonic() - started)))
        except (BrokenPipeError, ConnectionResetError):
            pass


class DualStackServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6
    daemon_threads = True

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def main():
    global ARGS, leds, button, camera
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--backend", default=os.getenv("REHOME_BACKEND", "http://localhost:8000"),
                        help="ReHome backend base URL (default: $REHOME_BACKEND or http://localhost:8000)")
    parser.add_argument("--zip", default=os.getenv("KIOSK_ZIP", "54311"), help="ZIP code donations are filed under")
    parser.add_argument("--site", default=os.getenv("KIOSK_SITE", ""),
                        help="public ReHome site; the thank-you screen shows a QR code to it")
    parser.add_argument("--fake", action="store_true", help="no GPIO; uses a test pattern unless --camera is given")
    parser.add_argument("--camera", default=None, help="v4l2 device (default: the first USB webcam)")
    parser.add_argument("--size", default="1280x720")
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--motion-threshold", type=float, default=6.0,
                        help="percent of the picture that must change to count as someone walking up")
    parser.add_argument("--open", action="store_true", help="allow clients from outside local networks")
    ARGS = parser.parse_args()
    ARGS.backend = ARGS.backend.rstrip("/")

    camera = Camera(ARGS.camera or ("test" if ARGS.fake else None), ARGS.size, ARGS.fps, ARGS.motion_threshold)
    leds = Leds(ARGS.fake)
    button = ButtonInput(ARGS.fake)
    leds.set("idle")

    server = DualStackServer(("::", ARGS.port), Handler)

    def on_term(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, on_term)
    log("system", f"kiosk on port {ARGS.port}, backend {ARGS.backend}, zip {ARGS.zip}" + (" (fake)" if ARGS.fake else ""))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        camera.stop()
        leds.close()
        button.close()


if __name__ == "__main__":
    main()
