<script>
  // Polls /api/events and shows each agent step. Used on /feed (demo screen).
  import { onMount } from 'svelte';
  import { getEvents } from '$lib/api.js';

  let events = $state([]);
  let error = $state('');

  onMount(() => {
    let last = 0;
    const tick = async () => {
      try {
        const { events: fresh } = await getEvents(last);
        if (fresh.length) {
          events = [...events, ...fresh].slice(-100);
          last = fresh.at(-1).id;
        }
        error = '';
      } catch {
        error = 'Can’t reach the backend. Is it running on port 8000?';
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  });
</script>

<section aria-live="polite">
  {#if error}<p class="error">{error}</p>{/if}
  {#if !events.length && !error}<p class="muted">Waiting for the first donation or request…</p>{/if}
  <ol>
    {#each events as e (e.id)}
      <li class={e.agent}>
        <span class="agent">{e.agent}</span>
        <span>{e.message}</span>
      </li>
    {/each}
  </ol>
</section>

<style>
  ol { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.5rem; }
  li { display: grid; grid-template-columns: 8rem 1fr; gap: 1rem; padding: 0.5rem 0; border-bottom: 1px solid #ddd; }
  .agent { font-weight: 600; }
  .parser .agent { color: #6b4fbb; }
  .requester .agent { color: #1f7a6d; }
  .error { color: #b00020; }
  .muted { color: #777; }
</style>
