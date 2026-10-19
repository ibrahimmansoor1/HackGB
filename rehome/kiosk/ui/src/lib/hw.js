// The kiosk hardware, through server.py: button, presence and camera events, LED patterns, photos.

/** Listen for hardware events. handlers: { state, button, presence, camera, leds, open, error }.
 *  EventSource reconnects by itself, and every new connection starts with a `state` event. */
export function connect(handlers) {
  const source = new EventSource('/hw/events');
  for (const kind of ['state', 'button', 'presence', 'camera', 'leds']) {
    source.addEventListener(kind, (e) => handlers[kind]?.(JSON.parse(e.data)));
  }
  source.onopen = () => handlers.open?.();
  source.onerror = () => handlers.error?.();
  return () => source.close();
}

/** Switch the LED pattern (server.py PATTERNS). `then` replaces the pattern a timed one ends in. */
export function leds(pattern, then) {
  fetch('/hw/leds', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(then ? { pattern, then } : { pattern })
  }).catch(() => {});
}

/** The current camera frame as a JPEG blob. */
export async function snap() {
  const res = await fetch('/hw/frame.jpg', { cache: 'no-store' });
  if (!res.ok) throw new Error("The camera isn't ready yet.");
  return res.blob();
}
