<script>
  // Polls /api/impact (Tiger continuous aggregate). Used on /feed.
  import { onMount } from 'svelte';
  import { getImpact } from '$lib/api.js';
  import Count from '$lib/Count.svelte';

  const TILES = [
    ['items_donated', 'Items donated'],
    ['matches_accepted', 'Neighbors helped'],
    ['requests_made', 'Requests'],
    ['prices_quoted', 'Prices quoted']
  ];

  let stats = $state(null);

  const top = $derived(
    Math.max(1, ...(stats?.by_category ?? []).map((c) => c.items_donated + c.matches_accepted))
  );

  onMount(() => {
    const tick = async () => {
      try { stats = await getImpact(); } catch { /* the feed shows connection errors */ }
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => clearInterval(id);
  });
</script>

{#if stats}
  <section aria-label="Impact">
    <div class="grid grid-cols-2 gap-3">
      {#each TILES as [key, label], i (key)}
        <div class="rounded-2xl border border-line bg-surface p-4">
          <strong class="block font-display text-4xl font-bold tabular-nums {i === 1 ? 'text-sage' : ''}">
            <Count value={stats.totals[key]} />
          </strong>
          <span class="text-sm text-ink-soft">{label}</span>
        </div>
      {/each}
    </div>

    {#if stats.by_category.length}
      <h3 class="mt-8 font-display text-lg font-bold">By category</h3>
      <ul class="mt-3 space-y-3">
        {#each stats.by_category as c (c.category)}
          <li>
            <div class="flex justify-between text-sm">
              <span class="capitalize">{c.category}</span>
              <span class="font-mono text-ink-soft">{c.items_donated} given · {c.matches_accepted} claimed</span>
            </div>
            <div class="mt-1.5 flex h-2 overflow-hidden rounded-full bg-ink/5">
              <div class="bg-lamp transition-[width] duration-700 ease-out"
                style="width: {(c.items_donated / top) * 100}%"></div>
              <div class="bg-sage transition-[width] duration-700 ease-out"
                style="width: {(c.matches_accepted / top) * 100}%"></div>
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  </section>
{/if}
