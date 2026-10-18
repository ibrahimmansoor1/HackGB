<script>
  // Polls /api/events and shows each agent step, newest first. Used on /feed (demo screen).
  import { onMount } from 'svelte';
  import { flip } from 'svelte/animate';
  import { BASE, getEvents } from '$lib/api.js';
  import { rise, glide } from '$lib/motion.js';

  const DOT = {
    parser: 'bg-[#8b74d4]', requester: 'bg-sage', pricing: 'bg-lamp', concierge: 'bg-[#4f86c6]',
    matchmaker: 'bg-[#d0648f]', orchestrator: 'bg-ink-soft/40'
  };

  let events = $state([]);
  let error = $state('');

  onMount(() => {
    let last = 0;
    let lost = false;   // backend was unreachable: its event ids may have restarted
    let timer;
    let alive = true;
    // One poll at a time (setTimeout, not setInterval): overlapping polls
    // appended the same events twice and crashed the keyed list.
    const tick = async () => {
      try {
        const { events: fresh } = await getEvents(lost ? 0 : last);
        if (lost) { events = []; last = 0; lost = false; }
        const added = fresh.filter((e) => e.id > last);
        if (added.length) {
          events = [...added.reverse(), ...events].slice(0, 60);
          last = events[0].id;
        }
        error = '';
      } catch {
        lost = true;
        error = `Can’t reach the backend at ${BASE}. Is it running?`;
      }
      if (alive) timer = setTimeout(tick, 1000);
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  });

  const time = (iso) => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' });
</script>

<section aria-live="polite">
  {#if error}<p class="text-brick">{error}</p>{/if}
  {#if !events.length && !error}<p class="text-ink-soft">Waiting for the first donation or request…</p>{/if}
  <ol class="divide-y divide-line">
    {#each events as e (e.id)}
      <li animate:flip={glide()} in:rise={{ y: -10 }} class="grid grid-cols-[7.5rem_1fr] gap-4 py-3">
        <span class="flex items-center gap-2 text-sm font-semibold">
          <span class="size-2 shrink-0 rounded-full {DOT[e.agent] ?? 'bg-ink-soft/40'}"></span>{e.agent}
        </span>
        <span class="text-sm">
          {e.message}
          <span class="ml-1 font-mono text-xs text-ink-soft">{time(e.created_at)}</span>
        </span>
      </li>
    {/each}
  </ol>
</section>
