<script>
  // Polls /api/impact (Tiger continuous aggregate). Used on /feed.
  import { onMount } from 'svelte';
  import { getImpact } from '$lib/api.js';

  const TILES = [
    ['items_donated', 'Items donated'],
    ['matches_accepted', 'Neighbors helped'],
    ['requests_made', 'Requests'],
    ['prices_quoted', 'Prices quoted']
  ];

  let stats = $state(null);

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
    <div class="tiles">
      {#each TILES as [key, label] (key)}
        <div class="tile"><strong>{stats.totals[key]}</strong><span>{label}</span></div>
      {/each}
    </div>
    {#if stats.by_category.length}
      <table>
        <thead><tr><th>Category</th><th>Donated</th><th>Claimed</th></tr></thead>
        <tbody>
          {#each stats.by_category as c (c.category)}
            <tr><td>{c.category}</td><td>{c.items_donated}</td><td>{c.matches_accepted}</td></tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>
{/if}

<style>
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr)); gap: 0.75rem; margin-bottom: 1rem; }
  .tile { border: 1px solid #ddd; border-radius: 0.5rem; padding: 0.75rem; display: grid; }
  .tile strong { font-size: 2rem; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; }
  th, td { text-align: left; padding: 0.25rem 0.5rem; border-bottom: 1px solid #eee; }
</style>
