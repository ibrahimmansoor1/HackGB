<script>
  // Coins thrown up out of the price on the "listed" screen, then falling away.
  const coins = Array.from({ length: 16 }, (_, i) => ({
    dx: `${(Math.random() * 2 - 1) * 11}rem`,
    up: `${-(5 + Math.random() * 7)}rem`,
    down: `${12 + Math.random() * 10}rem`,
    spin: `${(Math.random() * 2 - 1) * 540}deg`,
    delay: `${i * 45 + Math.random() * 60}ms`,
    size: `${1.8 + Math.random() * 1.1}rem`
  }));
</script>

<div class="pointer-events-none absolute top-1/2 left-1/2 z-10" aria-hidden="true">
  {#each coins as c}
    <span class="absolute [animation:coin-x_1.6s_linear_both]" style:--dx={c.dx} style:animation-delay={c.delay}>
      <span class="grid -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-lamp font-display font-bold text-night shadow-[inset_0_-0.15rem_0_rgb(0_0_0/0.25)] ring-2 ring-[#f6c97a] [animation:coin-y_1.6s_cubic-bezier(0.2,0.8,0.4,1)_both]"
        style:--up={c.up} style:--down={c.down} style:--spin={c.spin} style:animation-delay={c.delay}
        style:width={c.size} style:height={c.size} style:font-size="calc({c.size} * 0.55)">$</span>
    </span>
  {/each}
</div>
