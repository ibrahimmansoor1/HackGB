// Shared motion for the task pages: slow, smooth, no overshoot.
// With reduced motion on, everything falls back to a short fade.
import { cubicOut } from 'svelte/easing';
import { crossfade, fade, fly } from 'svelte/transition';

export const reduced = () =>
  typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Fade in while drifting up a few pixels. */
export function rise(node, { delay = 0, y = 12, duration = 550 } = {}) {
  return reduced()
    ? fade(node, { delay, duration: 200 })
    : fly(node, { delay, y, duration, easing: cubicOut, opacity: 0 });
}

/** Options for animate:flip when a keyed list reorders. */
export const glide = () => ({ duration: reduced() ? 0 : 700, easing: cubicOut });

/** Cards that move between two lists glide from one spot to the other. */
export const [send, receive] = crossfade({
  duration: (d) => (reduced() ? 0 : Math.min(800, Math.max(450, Math.sqrt(d) * 25))),
  easing: cubicOut,
  fallback: (node) => fade(node, { duration: reduced() ? 0 : 300 })
});
