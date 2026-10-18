<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import Camera from '@lucide/svelte/icons/camera';
  import HandHeart from '@lucide/svelte/icons/hand-heart';
  import ArrowRight from '@lucide/svelte/icons/arrow-right';
  import Sparkles from '@lucide/svelte/icons/sparkles';
  import House from '@lucide/svelte/icons/house';
  import { listItems } from '$lib/api.js';
  import { setPendingPhoto } from '$lib/pending.js';
  import AsciiHome from '$lib/landing/AsciiHome.svelte';
  import WireFigure from '$lib/landing/WireFigure.svelte';
  import ItemTag from '$lib/landing/ItemTag.svelte';
  import LiveActivity from '$lib/landing/LiveActivity.svelte';
  import { photo, context, rehome } from '$lib/landing/figures.js';

  const STEPS = [
    { draw: photo, title: 'One photo becomes a listing' },
    { draw: context, title: 'Ask the way you’d ask a friend' },
    { draw: rehome, title: 'Matched with someone nearby' }
  ];

  // Shown when the backend isn't running, so the page never looks empty.
  const EXAMPLE_ITEMS = [
    { id: 'ex1', category: 'outerwear', item: 'puffer jacket', color: 'black', size: 'M', condition: 'like new' },
    { id: 'ex2', category: 'footwear', item: 'snow boots', color: 'brown', size: '9', condition: 'good' },
    { id: 'ex3', category: 'home', item: 'wool blanket', color: 'beige', size: null, condition: 'good' },
    { id: 'ex4', category: 'accessories', item: 'knit beanie', color: 'red', size: null, condition: 'new' }
  ];
  const TILTS = [-2.5, 1.5, -1, 2];

  let home = $state();
  let need = $state('');
  let available = $state(null); // null until the backend answers
  let recent = $state([]);
  let hovered = $state(-1);

  const items = $derived(recent.length ? recent : EXAMPLE_ITEMS);

  onMount(async () => {
    try {
      const { items } = await listItems('available');
      available = items.length;
      recent = items.toSorted((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 4);
    } catch {
      // Backend not running: keep the example tags.
    }
  });

  function pickPhoto(e) {
    const file = e.currentTarget.files?.[0];
    if (!file) return;
    setPendingPhoto(file);
    goto('/donate');
  }

  function ask(e) {
    e.preventDefault();
    const q = need.trim();
    goto(q ? `/request?q=${encodeURIComponent(q)}` : '/request');
  }
</script>

<!-- Hero: a night window with the ASCII home, and the two ways in -->
<section class="px-4 sm:px-6">
  <div class="relative mx-auto max-w-6xl">
    <div class="pt-4 pb-6 lg:pointer-events-none lg:absolute lg:inset-y-0 lg:left-0 lg:z-10 lg:flex lg:w-[50%] lg:flex-col lg:justify-center lg:p-14 lg:pb-28">
      <h1 class="font-display text-[clamp(2.6rem,6vw,4.75rem)] leading-[0.95] font-bold tracking-[-0.035em] text-ink lg:text-night-ink">
        Good things deserve a <span class="text-lamp-ink lg:text-lamp">second home.</span>
      </h1>
      <p class="mt-5 max-w-md text-lg text-pretty text-ink-soft lg:max-w-sm lg:text-night-soft">
        Sell or give away what you don’t use with one photo. Need something? Ask in one sentence. Our AI helpers
        handle everything in between.
      </p>
    </div>

    <div class="relative h-[340px] overflow-hidden rounded-[2rem] bg-night sm:h-[460px] lg:h-[620px]">
      <AsciiHome bind:this={home} />
      <div class="pointer-events-none absolute inset-y-0 left-0 hidden w-3/5 bg-linear-to-r from-night via-night/85 to-transparent lg:block"></div>
      {#if available !== null}
        <p class="absolute top-5 right-6 flex items-center gap-2 font-mono text-xs text-night-soft">
          <span class="size-1.5 animate-pulse rounded-full bg-lamp"></span>
          {available} things looking for a new home
        </p>
      {/if}
    </div>
  </div>

  <div class="relative z-20 mx-auto -mt-14 grid max-w-5xl gap-4 sm:px-2 md:grid-cols-2 lg:-mt-24">
    <div
      role="group"
      aria-labelledby="give-title"
      class="rounded-[1.75rem] bg-surface p-6 shadow-[0_28px_50px_-30px_rgb(29_21_34/0.5)] ring-1 ring-line sm:p-7"
      onpointerenter={() => home?.launch('give')}
    >
      <div class="flex items-center gap-3">
        <span class="grid size-11 place-items-center rounded-2xl bg-lamp text-night"><Camera class="size-5" /></span>
        <h2 id="give-title" class="font-display text-2xl font-semibold tracking-tight">Give something</h2>
      </div>
      <p class="mt-3 text-ink-soft">One photo. Then donate it or sell it.</p>
      <div class="mt-6 flex flex-wrap items-center gap-x-4 gap-y-3">
        <label
          class="inline-flex cursor-pointer items-center gap-2 rounded-full bg-lamp px-5 py-3 font-semibold text-night transition hover:brightness-105 has-focus-visible:outline-2 has-focus-visible:outline-offset-3 has-focus-visible:outline-lamp-ink"
        >
          <Camera class="size-4.5" />
          Take or upload a photo
          <input id="give-photo" type="file" accept="image/*" class="sr-only" onchange={pickPhoto} />
        </label>
        <a href="/donate" class="text-sm font-medium text-ink-soft underline-offset-4 hover:text-ink hover:underline">
          or describe it in words
        </a>
      </div>
    </div>

    <form
      aria-labelledby="help-title"
      class="rounded-[1.75rem] bg-surface p-6 shadow-[0_28px_50px_-30px_rgb(29_21_34/0.5)] ring-1 ring-line sm:p-7"
      onpointerenter={() => home?.launch('help')}
      onsubmit={ask}
    >
      <div class="flex items-center gap-3">
        <span class="grid size-11 place-items-center rounded-2xl bg-sage text-on-sage"><HandHeart class="size-5" /></span>
        <h2 id="help-title" class="font-display text-2xl font-semibold tracking-tight">Get help</h2>
      </div>
      <p class="mt-3 text-ink-soft">Say it the way you’d tell a friend.</p>
      <label for="need" class="sr-only">What do you need?</label>
      <div class="mt-6 flex items-center gap-1 rounded-full bg-ground p-1.5 ring-1 ring-line focus-within:ring-2 focus-within:ring-sage">
        <input
          id="need"
          bind:value={need}
          placeholder="Snow clothes, moving to Chicago"
          autocomplete="off"
          class="min-w-0 flex-1 bg-transparent px-4 py-2 outline-none placeholder:text-ink-soft/70"
        />
        <button class="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-sage px-4 py-2.5 font-semibold text-on-sage transition hover:brightness-110">
          <span class="max-sm:sr-only">Find it</span> <ArrowRight class="size-4" />
        </button>
      </div>
    </form>
  </div>
</section>

<!-- How it works: three line drawings that come alive on hover -->
<section id="how" class="mx-auto max-w-6xl scroll-mt-6 px-4 pt-28 pb-24 sm:px-6">
  <p class="flex items-center gap-2 font-mono text-sm text-lamp-ink">
    <span class="grid size-6 place-items-center rounded-md bg-lamp/15"><Sparkles class="size-3.5" /></span>
    How it works
  </p>
  <h2 class="mt-4 max-w-2xl font-display text-4xl leading-[1.05] font-semibold tracking-[-0.025em] sm:text-5xl">
    A small team of AI helpers does the legwork.
  </h2>
  <a href="/feed" class="mt-8 inline-flex items-center gap-2 rounded-full bg-ink/7 px-5 py-2.5 font-medium transition hover:bg-ink/12">
    Watch them work <ArrowRight class="size-4" />
  </a>

  <div class="mt-16 grid gap-y-14 md:grid-cols-3">
    {#each STEPS as step, i}
      <article
        class="flex flex-col border-l border-line pr-2 pl-5"
        onpointerenter={() => (hovered = i)}
        onpointerleave={() => (hovered = -1)}
      >
        <span class="font-mono text-xs text-ink-soft">{i + 1}</span>
        <div class="mx-auto aspect-square w-full max-w-[22rem]">
          <WireFigure draw={step.draw} active={hovered === i} />
        </div>
        <h3 class="font-display text-xl font-semibold tracking-tight">{step.title}</h3>
      </article>
    {/each}
  </div>
</section>

<!-- What's in the pool right now, and the agents at work -->
<section class="mx-auto max-w-6xl px-4 pb-28 sm:px-6">
  <div class="grid gap-14 lg:grid-cols-[1.35fr_1fr] lg:gap-16">
    <div>
      <div class="flex flex-wrap items-baseline justify-between gap-3">
        <h2 class="font-display text-3xl font-semibold tracking-tight sm:text-4xl">Looking for a new home</h2>
        <p class="font-mono text-xs text-ink-soft">
          {recent.length ? `${available} available now` : 'example items'}
        </p>
      </div>
      <div class="mt-8 grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-4">
        {#each items as item, i (item.id)}
          <ItemTag {item} tilt={TILTS[i % TILTS.length]} />
        {/each}
      </div>
    </div>

    <div>
      <h2 class="font-display text-3xl font-semibold tracking-tight sm:text-4xl">Watch the helpers work</h2>
      <div class="mt-8"><LiveActivity /></div>
    </div>
  </div>
</section>

<footer>
  <div aria-hidden="true" class="overflow-hidden font-mono text-[10px] leading-[0.9] tracking-[0.25em] whitespace-nowrap text-line select-none">
    {'v'.repeat(320)}<br />{'v'.repeat(320)}
  </div>
  <div class="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-ink-soft sm:px-6">
    <span class="flex items-center gap-2 font-display text-base font-semibold text-ink">
      <House class="size-4" /> ReHome
    </span>
    <span>Made in 24 hours at HackGB 2026, UW–Green Bay</span>
  </div>
</footer>
