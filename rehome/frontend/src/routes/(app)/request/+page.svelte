<script>
  import { onMount } from 'svelte';
  import { flip } from 'svelte/animate';
  import { fade } from 'svelte/transition';
  import { page } from '$app/state';
  import ArrowRight from '@lucide/svelte/icons/arrow-right';
  import MapPin from '@lucide/svelte/icons/map-pin';
  import Check from '@lucide/svelte/icons/check';
  import { listItems, requestItem, acceptMatch } from '$lib/api.js';
  import ItemPhoto from '$lib/ItemPhoto.svelte';
  import { rise, glide, send, receive } from '$lib/motion.js';
  import { loadZip, saveZip } from '$lib/zip.js';

  // The landing page passes what you typed as ?q=
  let text = $state(page.url.searchParams.get('q') ?? '');
  let zip = $state('');
  let available = $state([]);
  let loading = $state(false);
  let error = $state('');
  let result = $state(null);
  let claiming = $state('');
  let claimed = $state(null);

  // Matches first; everything else still available underneath.
  const matches = $derived(result?.matches ?? []);
  const others = $derived.by(() => {
    const picked = new Set(matches.map((m) => m.item_id));
    return available.filter((i) => !picked.has(i.id));
  });

  onMount(async () => {
    zip = loadZip();
    try { available = (await listItems()).items; } catch { /* the search still works */ }
    if (text && zip) submit();
  });

  async function submit() {
    if (!text.trim()) { error = 'Tell us what you need.'; return; }
    if (!/^\d{5}$/.test(zip)) { error = 'Add your 5-digit zip code.'; return; }
    saveZip(zip);
    loading = true; error = ''; result = null; claimed = null;
    try { result = await requestItem({ text, zip }); }
    catch (e) { error = e.message; }
    finally { loading = false; }
  }

  async function claim(m) {
    claiming = m.item_id; error = '';
    try {
      claimed = { ...(await acceptMatch(result.request_id, m.item_id)), item: m.item, title: m.title };
      available = available.filter((i) => i.id !== m.item_id);
    } catch (e) { error = e.message; }
    finally { claiming = ''; }
  }
</script>

<div class="mx-auto max-w-5xl">
  <h1 class="font-display text-4xl font-bold tracking-tight sm:text-5xl">Find something</h1>

  <form class="mt-6 flex flex-col gap-3 sm:flex-row sm:items-stretch"
    onsubmit={(e) => { e.preventDefault(); submit(); }}>
    <label class="sr-only" for="need">What do you need?</label>
    <input id="need" bind:value={text} autocomplete="off"
      placeholder="A warm coat, I’m moving to Chicago in December"
      class="min-w-0 flex-1 rounded-full border border-line bg-surface px-5 py-3.5 text-lg shadow-sm outline-none transition focus:border-ink-soft" />
    <div class="flex gap-3">
      <label class="flex items-center gap-1.5 rounded-full border border-line bg-surface px-4 text-ink-soft shadow-sm focus-within:border-ink-soft">
        <MapPin class="size-4 shrink-0" />
        <span class="sr-only">Zip code</span>
        <input bind:value={zip} inputmode="numeric" maxlength="5" placeholder="Zip"
          class="w-14 bg-transparent py-3.5 text-ink outline-none" />
      </label>
      <button type="submit" disabled={loading}
        class="inline-flex items-center gap-2 rounded-full bg-sage px-6 font-semibold text-on-sage shadow-sm transition hover:brightness-110 disabled:cursor-progress disabled:opacity-70">
        {loading ? 'Looking…' : 'Find it'}
        <ArrowRight class="size-4" />
      </button>
    </div>
  </form>

  {#if error}<p role="alert" class="mt-3 text-brick" transition:fade>{error}</p>{/if}

  {#if result?.query.inferred_context.length && !claimed}
    <div class="mt-5 flex flex-wrap items-center gap-2 text-sm">
      <span class="text-ink-soft">We took into account</span>
      {#each result.query.inferred_context as c, i (c)}
        <span in:rise={{ delay: 150 + i * 90, y: 6 }}
          class="rounded-full bg-lamp/15 px-3 py-1 font-medium text-lamp-ink">{c}</span>
      {/each}
    </div>
  {/if}

  {#if claimed}
    <section class="mx-auto mt-10 max-w-md text-center" in:rise={{ delay: 250 }}>
      <div class="mx-auto aspect-square w-56 overflow-hidden rounded-3xl border border-line shadow-lg">
        <ItemPhoto item={claimed.item} />
      </div>
      <p class="mt-6 inline-flex items-center gap-2 rounded-full bg-sage/15 px-3 py-1 text-sm font-semibold text-sage">
        <Check class="size-4" /> Reserved for you
      </p>
      <h2 class="mt-3 font-display text-3xl font-bold">It’s yours: {claimed.item.color} {claimed.title}</h2>
      <p class="mt-2 text-ink-soft">{claimed.handoff.message}</p>
      <button onclick={() => { claimed = null; result = null; text = ''; }}
        class="mt-6 rounded-full border border-line px-5 py-2.5 font-semibold transition hover:bg-ink/5">
        Find something else
      </button>
    </section>
  {:else}
    {#if result}
      <section class="mt-8">
        <h2 class="font-display text-2xl font-bold">
          {matches.length ? 'Picked for you' : 'No close match yet'}
        </h2>
        {#if !matches.length}
          <p class="mt-1 text-ink-soft">Your request stays open. We’ll match it when something fits.</p>
        {/if}
        <div class="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-3">
          {#each matches as m (m.item_id)}
            <article animate:flip={glide()} in:receive={{ key: m.item_id }} out:send={{ key: m.item_id }}
              class="group flex flex-col overflow-hidden rounded-3xl border bg-surface shadow-sm transition-shadow hover:shadow-md
                {m.rank === 1 ? 'border-lamp ring-2 ring-lamp/40' : 'border-line'}">
              <div class="relative aspect-4/3 overflow-hidden">
                <ItemPhoto item={m.item} class="transition-transform duration-700 ease-out group-hover:scale-[1.03]" />
                {#if m.rank === 1}
                  <span class="absolute left-3 top-3 rounded-full bg-lamp px-2.5 py-0.5 text-xs font-semibold text-night">Best match</span>
                {/if}
              </div>
              <div class="flex flex-1 flex-col p-4">
                <h3 class="font-semibold capitalize">{m.item.color} {m.title}</h3>
                <p class="text-sm text-ink-soft">{m.item.size ? `Size ${m.item.size} · ` : ''}{m.item.condition}</p>
                <p class="mt-2 line-clamp-2 text-sm">{m.reason}</p>
                <div class="mt-auto pt-4">
                  <button onclick={() => claim(m)} disabled={!!claiming}
                    class="rounded-full px-4 py-2 text-sm font-semibold transition disabled:opacity-60
                      {m.rank === 1 ? 'bg-ink text-ground hover:bg-ink/85' : 'border border-line hover:bg-ink/5'}">
                    {claiming === m.item_id ? 'Claiming…' : 'Claim this'}
                  </button>
                </div>
              </div>
            </article>
          {/each}
        </div>
      </section>
    {/if}

    {#if others.length}
      <section class="mt-10">
        <h2 class="font-display text-xl font-bold {result ? 'text-ink-soft' : ''}">
          {result ? 'Also available' : 'Available near you'}
          <span class="ml-1 font-mono text-sm font-normal text-ink-soft">{others.length}</span>
        </h2>
        <div class="mt-4 grid grid-cols-2 gap-4 transition-opacity duration-500 sm:grid-cols-4 lg:grid-cols-6
          {loading ? 'animate-pulse opacity-50' : ''}">
          {#each others as item, i (item.id)}
            <div animate:flip={glide()} in:receive={{ key: item.id }} out:send={{ key: item.id }}
              class="overflow-hidden rounded-2xl border border-line bg-surface">
              <div class="aspect-square overflow-hidden"><ItemPhoto {item} /></div>
              <p class="truncate px-3 py-2 text-sm font-medium capitalize">{item.item}
                {#if item.size}<span class="font-normal text-ink-soft"> · {item.size}</span>{/if}</p>
            </div>
          {/each}
        </div>
      </section>
    {/if}
  {/if}
</div>
