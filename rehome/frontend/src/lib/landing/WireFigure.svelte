<script>
  // Draws one of the line figures from figures.js as SVG. Animates toward
  // t = 1 while `active` (hover/focus) and eases back to rest afterwards.
  // On touch screens, which can't hover, it plays while scrolled into view.
  import { onMount, untrack } from 'svelte';

  let { draw, active = false } = $props();

  let el;
  let t = $state(0);
  let clock = $state(0);
  let shot = $state(0);
  let inView = $state(false);
  let touch = $state(false);

  const scene = $derived(draw(t, clock, shot));
  const on = $derived(active || (touch && inView));

  // Accent colors stay grey at rest and warm up as the figure comes alive.
  const tint = (tone) =>
    tone === 'ink' ? 'var(--ink)' : `color-mix(in oklab, var(--${tone}) ${Math.round(t * 100)}%, var(--ink-soft))`;

  onMount(() => {
    touch = matchMedia('(hover: none)').matches;
    const io = new IntersectionObserver(([e]) => (inView = e.isIntersecting), { threshold: 0.6 });
    io.observe(el);
    return () => io.disconnect();
  });

  $effect(() => {
    const target = on ? 1 : 0;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      t = target;
      shot = target ? 10 : 0; // jump straight to the finished state
      return;
    }
    // A hover that starts from rest replays the figure's sequence.
    if (target === 1 && untrack(() => t) < 0.05) shot = 0;
    let raf = 0;
    let last = performance.now();
    const tick = (now) => {
      const dt = Math.min(0.05, Math.max(0, (now - last) / 1000));
      last = now;
      t += (target - t) * Math.min(1, dt * 3.2);
      clock += dt * t;
      shot += dt;
      if (target === 0 && t < 0.002) {
        t = 0;
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  });
</script>

<svg bind:this={el} viewBox="-175 -175 350 350" class="block size-full overflow-visible text-ink" fill="none" aria-hidden="true">
  {#each scene.paths as p}
    <path
      d={p.d}
      stroke="currentColor"
      stroke-width="1"
      stroke-linecap="round"
      stroke-linejoin="round"
      vector-effect="non-scaling-stroke"
      stroke-dasharray={p.style === 'dotted' ? '0.01 4' : undefined}
      stroke-opacity={(p.style === 'dotted' ? 0.45 : p.tone ? 0.6 + 0.3 * t : 0.6) * p.opacity}
      style:color={p.tone ? tint(p.tone) : undefined}
    />
  {/each}
  {#each scene.marks as m}
    {#if m.opacity > 0.01}
      <circle cx={m.x} cy={m.y} r={m.size} fill="currentColor" opacity={m.opacity} style:color={tint(m.tone)} />
    {/if}
  {/each}
  {#each scene.labels as l}
    {#if l.opacity > 0.01}
      <text x={l.x} y={l.y} text-anchor="middle" class="fill-ink-soft font-mono text-[12px]" opacity={l.opacity}>
        {l.text}
      </text>
    {/if}
  {/each}
</svg>
