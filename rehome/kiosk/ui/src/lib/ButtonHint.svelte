<script>
  // The kiosk's physical button, drawn: a lamp-colored cap in a ring. `progress` (0 to 1) fills
  // the ring while the button is held; `pulse` breathes like the D5 LED does.
  let { label = '', progress = 0, pulse = false, size = '2.75rem' } = $props();

  const R = 21;
  const C = 2 * Math.PI * R;
</script>

<span class="inline-flex items-center gap-4">
  <svg viewBox="0 0 48 48" style:width={size} style:height={size} class="shrink-0 -rotate-90" aria-hidden="true">
    <circle cx="24" cy="24" r={R} fill="none" stroke-width="3" class="stroke-night-line" />
    <circle cx="24" cy="24" r={R} fill="none" stroke-width="3" stroke-linecap="round" class="stroke-lamp"
      stroke-dasharray={C} stroke-dashoffset={C * (1 - progress)} opacity={progress > 0 ? 1 : 0} />
    <circle cx="24" cy="24" r="13" class={['fill-lamp', pulse && 'animate-breathe']} />
  </svg>
  {#if label}
    <span class="font-mono text-lg text-night-soft">{label}</span>
  {/if}
</span>
