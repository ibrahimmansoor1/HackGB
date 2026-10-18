<script>
  // Compact agent-activity preview for the landing page. The full-screen
  // version for the demo laptop is $lib/ActivityFeed.svelte at /feed.
  import { onMount } from 'svelte';
  import { getEvents } from '$lib/api.js';

  const EXAMPLE = [
    { id: 'e1', agent: 'parser', message: 'Identified black Columbia puffer jacket, size M', time: '14:02:01' },
    { id: 'e2', agent: 'orchestrator', message: 'Saved itm_0142; searchable now', time: '14:02:03' },
    { id: 'e3', agent: 'requester', message: 'Inferred snow and sub-freezing winters; needs insulated, water-resistant', time: '14:02:10' },
    { id: 'e4', agent: 'orchestrator', message: 'Found 3 matches for req_0031', time: '14:02:11' },
    { id: 'e5', agent: 'orchestrator', message: 'Reserved itm_0142; donor notified', time: '14:02:20' }
  ];

  const AGENT_COLOR = { parser: 'text-lamp-ink', pricing: 'text-brick', requester: 'text-sage', orchestrator: 'text-ink-soft' };

  let events = $state([]);
  const live = $derived(events.length > 0);
  const rows = $derived(live ? events : EXAMPLE);

  const clock = (iso) =>
    new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });

  onMount(() => {
    let last = 0;
    let lost = false;   // backend was unreachable: its event ids may have restarted
    let delay = 2000;
    let timer;
    let alive = true;
    const tick = async () => {
      try {
        const { events: fresh } = await getEvents(lost ? 0 : last);
        if (lost) { events = []; last = 0; lost = false; }
        const added = fresh.filter((e) => e.id > last);
        if (added.length) {
          last = added.at(-1).id;
          events = [...events, ...added.map((e) => ({ ...e, time: clock(e.created_at) }))].slice(-5);
        }
        delay = 2000;
      } catch {
        // Backend not running: keep showing the example rows and check back less often.
        lost = true;
        delay = Math.min(delay * 2, 30000);
      }
      if (alive) timer = setTimeout(tick, delay);
    };
    tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  });
</script>

<div class="rounded-3xl bg-night p-5 text-night-ink sm:p-6">
  <div class="flex items-center justify-between gap-3 font-mono text-xs text-night-soft">
    <span class="flex items-center gap-2">
      <span class="size-2 rounded-full {live ? 'animate-pulse bg-lamp' : 'bg-night-soft/50'}"></span>
      {live ? 'live' : 'example run'}
    </span>
    <a href="/feed" class="rounded-full px-2 py-1 hover:bg-white/10 hover:text-night-ink">open full feed →</a>
  </div>
  <ol class="mt-4 flex flex-col gap-3 font-mono text-[0.8rem] leading-snug" aria-live="polite">
    {#each rows as e (e.id)}
      <li class="grid grid-cols-[4.5rem_7.5rem_1fr] gap-2 max-sm:grid-cols-[7rem_1fr]">
        <span class="text-night-soft/70 tabular-nums max-sm:hidden">{e.time}</span>
        <span class="{AGENT_COLOR[e.agent] ?? 'text-night-soft'} dark-lift">{e.agent}</span>
        <span>{e.message}</span>
      </li>
    {/each}
  </ol>
</div>

<style>
  /* The panel is always dark, so lift the theme's agent colors to their bright variants. */
  .dark-lift.text-lamp-ink { color: #f6bd66; }
  .dark-lift.text-sage { color: #a2c19b; }
  .dark-lift.text-brick { color: #e0805f; }
  .dark-lift.text-ink-soft { color: #c5b2bf; }
</style>
