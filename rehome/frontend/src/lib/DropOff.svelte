<script>
  // Shown when the pricing agent values an item under $10: selling isn't worth
  // the donor's time, so point them at the nearest Goodwill or recycling drop-off.
  // `after` = the item was already donated or listed; word it as a fallback.
  let { item, zip, price, after = false } = $props();

  const TEXTILES = ['outerwear', 'tops', 'bottoms', 'footwear', 'accessories', 'kids'];
  const recycler = $derived(
    item.category === 'electronics' ? 'electronics recycling'
      : TEXTILES.includes(item.category) ? 'textile recycling'
      : 'recycling center'
  );
  // Worn items are better recycled than resold, so lead with recycling for those.
  const worn = $derived(item.condition === 'fair');
  const spots = $derived.by(() => {
    const goodwill = { label: 'Goodwill', q: 'Goodwill' };
    const recycle = { label: recycler[0].toUpperCase() + recycler.slice(1), q: recycler };
    return worn ? [recycle, goodwill] : [goodwill, recycle];
  });
  const maps = (place) =>
    `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${place} near ${zip}`)}`;
</script>

<div class="mt-4 rounded-2xl border border-line bg-surface p-4">
  <p class="!mt-0 font-semibold">
    Worth about ${price.low}–${price.high}, so selling it probably isn't worth your time.
  </p>
  <p class="text-sm text-ink-soft">
    {#if after}
      If nobody nearby claims it, these places will take it.
    {:else if worn}
      It looks worn, so a recycler is the best home for it. Goodwill takes it too.
    {:else}
      Drop it off nearby instead, or donate it here so a neighbor can claim it.
    {/if}
  </p>
  <p class="flex flex-wrap gap-x-5 gap-y-1 text-sm font-semibold">
    {#each spots as s (s.q)}
      <a class="underline underline-offset-4" href={maps(s.q)} target="_blank" rel="noopener noreferrer">
        {s.label} near {zip} ↗
      </a>
    {/each}
  </p>
</div>
