<script>
  // The ReHome kiosk: walk up, hold something to the camera, press the button. The photo is
  // parsed into a draft, and nothing is saved until the person chooses:
  //
  //   attract -> countdown -> parsing -> result --press--> donating -> thanks -> attract
  //                                        |hold
  //                                     pricing -> quote --press--> sold -> thanks
  //                                                  |hold -> donating
  //   any failure -> error (press to try again); press three times quickly -> attract, from anywhere
  //
  // Marketplace listing isn't wired up yet, so "sold" only celebrates; nothing is posted.
  // The physical button, the space bar, and tapping the screen are all "the button".
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { cubicIn, cubicOut } from 'svelte/easing';
  import AsciiMirror from './lib/AsciiMirror.svelte';
  import ButtonHint from './lib/ButtonHint.svelte';
  import CoinBurst from './lib/CoinBurst.svelte';
  import HangTag from './lib/HangTag.svelte';
  import Polaroid from './lib/Polaroid.svelte';
  import Qr from './lib/Qr.svelte';
  import Steps from './lib/Steps.svelte';
  import * as api from './lib/api.js';
  import * as hw from './lib/hw.js';
  import * as sound from './lib/sound.js';

  const HOLD_MS = 1200; // a press held this long is a "hold"
  const SLEEP_AFTER = 45_000; // dim the attract screen when nobody has been around this long
  const MIN_WORKING = 2800; // let the print develop even when the backend answers at once

  // What the backend is doing on each working screen
  const WORKING = {
    parsing: 'Reading the tag…',
    donating: 'Putting it on the shelf…',
    pricing: 'Checking prices…',
    listing: 'Listing it…'
  };
  const PHOTO_SCREENS = [...Object.keys(WORKING), 'result', 'quote', 'sold', 'error'];

  let screen = $state('attract');
  let config = $state({ zip: '54311', site: '' });
  let awake = $state(false);
  let present = $state(false);
  let camera = $state('starting');
  let backend = $state('unknown');
  let count = $state(3);
  let flashing = $state(false);
  let photo = $state(null); // object URL of the captured frame
  let draft = $state(null); // { draft_id, item }
  let offer = $state(null); // the pricing agent's quote
  let listing = $state(null);
  let thanksLine = $state('');
  let problem = $state('');
  let steps = $state([]);
  let holdProgress = $state(0);

  let cursor = 0; // newest agent event id already seen
  let lastSeen = 0;
  let changedAt = 0;
  let timer, holdFrame;
  let hold = null; // { short, long } while the button is held on a choice screen
  let stale = false; // server.py restarted; reload when back on the attract screen
  let flow = 0; // bumped on every reset, so a cancelled flow's late backend answers are ignored
  let taps = []; // recent press times, to spot a triple press
  let pendingShort; // a short press waits a moment in case it's the start of a triple press

  const asciiOpacity = $derived(
    screen === 'attract' ? (awake ? 1 : 0.6) : screen === 'thanks' ? 0.45 : 0.1
  );
  const askPrice = $derived(
    offer ? Math.round((offer.suggested_price.low + offer.suggested_price.high) / 2) : 0
  );
  const money = (n) => `$${Number.isInteger(n) ? n : n.toFixed(2)}`;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, Math.max(0, ms)));

  function go(next) {
    screen = next;
    changedAt = performance.now();
    clearTimeout(timer);
    if (next in WORKING) hw.leds('thinking');
    else if (next === 'attract') hw.leds(awake ? 'ready' : 'idle');
    else if (next === 'result' || next === 'quote') {
      hw.leds('ready');
      timer = setTimeout(reset, 40_000); // walked away: the draft is simply dropped
    } else if (next === 'sold') {
      hw.leds('success', 'ready');
      sound.chaChing();
      timer = setTimeout(finish, 7000);
    } else if (next === 'thanks') {
      hw.leds('success');
      sound.chime();
      timer = setTimeout(reset, 9000);
    } else if (next === 'error') {
      hw.leds('error', 'ready');
      timer = setTimeout(reset, 20_000);
    }
  }

  function clearPhoto() {
    const old = photo;
    photo = draft = offer = listing = null;
    problem = '';
    steps = [];
    if (old) setTimeout(() => URL.revokeObjectURL(old), 3000); // after the print has flown away
  }

  function reset() {
    if (stale) return location.reload();
    flow++;
    stopHold();
    clearTimeout(pendingShort);
    clearPhoto();
    go('attract');
  }

  function finish() {
    thanksLine = 'unsold in 30 days? it goes to the donation shelf';
    go('thanks');
  }

  function fail(e) {
    console.error(e);
    problem = e?.message || String(e);
    go('error');
  }

  // ---------------------------------------------------------------- agent steps

  async function syncCursor() {
    try {
      for (const e of await api.events(cursor)) cursor = Math.max(cursor, e.id);
    } catch {}
  }

  async function pollSteps() {
    try {
      for (const e of await api.events(cursor)) {
        cursor = Math.max(cursor, e.id);
        steps.push(e);
      }
    } catch {}
  }

  /** Show a working screen while a backend call runs, streaming agent steps, for at least `min` ms. */
  async function working(next, firstStep, call, min = MIN_WORKING) {
    steps = [{ id: `kiosk-${next}`, agent: 'kiosk', message: firstStep }];
    go(next);
    const started = performance.now();
    const poll = setInterval(pollSteps, 600);
    try {
      const result = await call();
      await sleep(min - (performance.now() - started));
      await pollSteps();
      return result;
    } finally {
      clearInterval(poll);
    }
  }

  // ---------------------------------------------------------------- the flow

  async function startCountdown() {
    const f = ++flow;
    clearPhoto();
    go('countdown');
    syncCursor();
    for (count = 3; count > 0; count--) {
      hw.leds('tick');
      sound.tick();
      await sleep(1000);
      if (f !== flow) return;
    }
    let blob;
    try {
      blob = await hw.snap();
    } catch (e) {
      return f === flow && fail(e);
    }
    if (f !== flow) return;
    flashing = true;
    requestAnimationFrame(() => (flashing = false));
    sound.shutter();
    hw.leds('flash', 'thinking');
    photo = URL.createObjectURL(blob);
    try {
      const parsed = await working('parsing', 'Photo taken', () => api.parse(blob, config.zip));
      if (f !== flow) return;
      draft = parsed;
      go('result');
    } catch (e) {
      if (f === flow) fail(e);
    }
  }

  async function donateIt() {
    const f = flow;
    try {
      await working('donating', 'Donating it', () => api.donate(draft.draft_id), 1400);
      if (f !== flow) return;
      thanksLine = `anyone nearby can find your ${draft.item.item} now`;
      go('thanks');
    } catch (e) {
      if (f === flow) fail(e);
    }
  }

  async function priceIt() {
    const f = flow;
    try {
      const quote = await working('pricing', 'Selling it instead', () => api.quote(draft.draft_id));
      if (f !== flow) return;
      offer = quote;
      go('quote');
    } catch (e) {
      // No quote is no reason to stop someone selling: list it without a price
      if (f !== flow) return;
      console.error(e);
      listIt();
    }
  }

  function listIt() {
    listing = { price: offer ? askPrice : null };
    go('sold');
  }

  // ---------------------------------------------------------------- input

  function wake() {
    lastSeen = Date.now();
    if (!awake) {
      awake = true;
      if (screen === 'attract') hw.leds('ready');
    }
  }

  function press() {
    sound.unlock();
    wake();
    const now = performance.now();
    taps = [...taps.filter((t) => now - t < 1200), now];
    if (taps.length >= 3) {
      taps = [];
      return reset(); // three quick presses: start over
    }
    clearTimeout(pendingShort); // a second quick press: whatever the first one meant is off
    if (now - changedAt < 350) return; // a bounce, or a press meant for the last screen
    if (screen === 'attract' || screen === 'thanks' || screen === 'error') startCountdown();
    else if (screen === 'result') startHold(donateIt, priceIt);
    else if (screen === 'quote') startHold(listIt, donateIt);
    else if (screen === 'sold') finish();
  }

  function release() {
    if (!hold) return;
    const { short } = hold;
    const f = flow;
    stopHold();
    pendingShort = setTimeout(() => f === flow && short(), 450);
  }

  function startHold(short, long) {
    hold = { short, long };
    const start = performance.now();
    const step = () => {
      if (!hold) return;
      // the ring only shows once it's clearly a hold, so a quick press doesn't flicker it
      const t = performance.now() - start;
      holdProgress = t < 150 ? 0 : Math.min(1, t / HOLD_MS);
      if (holdProgress < 1) holdFrame = requestAnimationFrame(step);
      else {
        stopHold();
        long();
      }
    };
    holdFrame = requestAnimationFrame(step);
  }

  function stopHold() {
    hold = null;
    holdProgress = 0;
    cancelAnimationFrame(holdFrame);
  }

  function onkeydown(e) {
    if (e.repeat) return;
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      press();
    } else if (e.key === 'Escape') reset();
  }

  function onkeyup(e) {
    if (e.key === ' ' || e.key === 'Enter') release();
  }

  // ---------------------------------------------------------------- setup

  onMount(() => {
    api.config().then((c) => (config = c)).catch(() => {});
    syncCursor();

    let boot;
    const disconnect = hw.connect({
      state: (s) => {
        // server.py restarted (a redeploy, say): reload for a new build of this page,
        // but not in the middle of someone's turn
        if (boot && s.boot !== boot) stale = true;
        if (stale && screen === 'attract') return location.reload();
        boot = s.boot;
        present = s.presence.present;
        camera = s.camera.status;
        if (present) wake();
        if (screen === 'attract') hw.leds(awake ? 'ready' : 'idle');
      },
      button: (b) => (b.pressed ? press() : release()),
      presence: (p) => {
        present = p.present;
        if (present) wake();
      },
      camera: (c) => (camera = c.status),
      error: () => (camera = 'disconnected')
    });

    const checkHealth = () =>
      api.health().then((h) => (backend = h.stubs ? 'stub' : 'live')).catch(() => (backend = 'down'));
    checkHealth();
    const healthTimer = setInterval(checkHealth, 20_000);

    const sleepTimer = setInterval(() => {
      if (awake && !present && Date.now() - lastSeen > SLEEP_AFTER) {
        awake = false;
        if (screen === 'attract') hw.leds('idle');
      }
    }, 1000);

    // Hide the pointer unless someone is moving a mouse
    let cursorTimer;
    const showCursor = () => {
      document.body.style.cursor = '';
      clearTimeout(cursorTimer);
      cursorTimer = setTimeout(() => (document.body.style.cursor = 'none'), 3000);
    };
    document.body.style.cursor = 'none';
    addEventListener('pointermove', showCursor);

    return () => {
      disconnect();
      clearInterval(healthTimer);
      clearInterval(sleepTimer);
      removeEventListener('pointermove', showCursor);
    };
  });
</script>

<svelte:window {onkeydown} {onkeyup} />

<main class="fixed inset-0 overflow-hidden bg-night text-night-ink" onpointerdown={press} onpointerup={release}
  onpointercancel={release}>
  <AsciiMirror opacity={asciiOpacity} />
  <div class="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_50%_40%,transparent_45%,rgb(20_16_23/0.55)_100%)]"
    aria-hidden="true"></div>
  <div class="pointer-events-none fixed inset-x-0 top-0 h-32 bg-[linear-gradient(to_bottom,rgb(20_16_23/0.9),transparent)] portrait:h-24"
    aria-hidden="true"></div>

  <header class="absolute top-10 right-12 left-12 flex portrait:top-6 portrait:right-6 portrait:left-6 items-center justify-between font-mono text-sm text-night-soft">
    <span class="font-display text-2xl font-semibold tracking-tight text-night-ink">ReHome</span>
    <span class="flex items-center gap-5">
      {#if camera !== 'running'}
        <span class="flex items-center gap-2">
          <span class="size-2 rounded-full bg-brick"></span>camera {camera}
        </span>
      {/if}
      <span class="flex items-center gap-2">
        <span class={['size-2 rounded-full', backend === 'down' ? 'bg-brick' : backend === 'unknown' ? 'bg-night-soft/40' : 'bg-sage']}></span>
        {backend === 'down' ? 'backend offline' : `kiosk · ${config.zip}`}
      </span>
    </span>
  </header>

  {#if screen === 'attract'}
    <section class="absolute inset-0 flex flex-col justify-end bg-[linear-gradient(to_top,rgb(20_16_23/0.92)_0%,rgb(20_16_23/0.75)_30%,transparent_55%)] px-16 pb-16 portrait:px-7 portrait:pb-14" transition:fade={{ duration: 900 }}>
      <h1 class="max-w-[13ch] font-display text-[5.25rem] leading-[0.95] portrait:text-[3.4rem] font-semibold tracking-tight">
        Good things deserve a second home.
      </h1>
      <div class={['mt-8 transition-opacity duration-[1200ms]', awake ? 'opacity-100' : 'opacity-0']}>
        <ButtonHint pulse label="hold it up to the camera, then press the button" />
      </div>
    </section>
  {/if}

  {#if screen === 'countdown'}
    <section class="absolute inset-0 flex flex-col items-center justify-center gap-7 portrait:px-6 portrait:text-center" in:fade={{ duration: 600 }}
      out:fade={{ duration: 400 }}>
      <div class="relative aspect-video w-[46rem] overflow-hidden portrait:w-[26rem] rounded-[1.6rem] bg-night-deep shadow-2xl ring-[0.55rem] ring-kraft">
        <img src="/hw/stream.mjpg?fps=15" alt="" class="size-full -scale-x-100 object-cover" />
        {#key count}
          <span class="absolute inset-0 grid animate-count place-items-center font-display text-[11rem] font-semibold text-lamp portrait:text-[7rem] [text-shadow:0_0.4rem_2.5rem_rgb(0_0_0/0.55)]">
            {count}
          </span>
        {/key}
      </div>
      <p class="font-mono text-lg text-night-soft">hold it still, with any tag facing the camera</p>
    </section>
  {/if}

  {#if photo && PHOTO_SCREENS.includes(screen)}
    <div class="absolute inset-y-0 left-0 grid w-[54%] place-items-center pl-8 portrait:inset-x-0 portrait:top-14 portrait:bottom-auto portrait:h-[33%] portrait:w-full portrait:pl-0"
      in:fly={{ y: -70, duration: 1100, easing: cubicOut }}
      out:fly={{ y: -260, duration: 1300, easing: cubicIn, opacity: 0 }}>
      <Polaroid src={photo} caption={draft?.item.item ?? 'developing…'} />
    </div>
  {/if}

  {#if PHOTO_SCREENS.includes(screen)}
    <div class="absolute inset-y-0 right-0 grid w-[46%] items-center pr-16 pl-4 *:[grid-area:1/1] portrait:top-[41%] portrait:right-0 portrait:bottom-10 portrait:left-0 portrait:w-full portrait:items-stretch portrait:px-7 portrait:pt-3">
      {#key screen}
        <div class="min-w-0 portrait:flex portrait:min-h-0 portrait:flex-col" in:fly={{ y: 22, duration: 800, delay: 250, easing: cubicOut }}
          out:fade={{ duration: 300 }}>
          {#if screen in WORKING}
            <h2 class="font-display text-[3.4rem] leading-none font-semibold tracking-tight portrait:text-[2.4rem]">{WORKING[screen]}</h2>
            <Steps {steps} />
          {:else if screen === 'result' && draft}
            <div class="portrait:-m-2 portrait:min-h-0 portrait:shrink portrait:overflow-hidden portrait:p-2"><HangTag item={draft.item} /></div>
            <div class="mt-12 flex shrink-0 flex-col gap-5 portrait:mt-auto portrait:gap-4 portrait:pt-4">
              <ButtonHint label="press · donate it" />
              <ButtonHint label="hold · sell it instead" progress={holdProgress} />
            </div>
          {:else if screen === 'quote' && offer}
            <p class="flex items-center gap-3 font-mono text-lg text-lamp">
              <span class="size-2.5 rounded-full bg-lamp"></span>
              {offer.basis === 'active listings' ? 'currently listed for, on eBay'
                : offer.basis === 'web search' ? 'going rate, from the web' : 'estimated price'}
            </p>
            <p class="mt-3 font-display text-[5.5rem] leading-none font-semibold tracking-tight portrait:text-[3.8rem]">
              ${Math.round(offer.suggested_price.low)}–{Math.round(offer.suggested_price.high)}
            </p>
            {#if offer.comps?.length}
              <ul class="mt-6 space-y-1.5 font-mono text-base text-night-soft">
                {#each offer.comps.slice(0, 2) as comp}
                  <li class="truncate"><span class="text-night-ink">{money(comp.price)}</span> · {comp.title}</li>
                {/each}
              </ul>
            {/if}
            <div class="mt-10 flex shrink-0 flex-col gap-5 portrait:mt-auto portrait:gap-4 portrait:pt-4">
              <ButtonHint label="press · list it for ${askPrice}" />
              <ButtonHint label="hold · donate it instead" progress={holdProgress} />
            </div>
          {:else if screen === 'sold' && listing}
            <p class="flex items-center gap-3 font-mono text-lg text-sage">
              <span class="size-2.5 rounded-full bg-sage"></span>listed for sale
            </p>
            <div class="relative mt-3 w-fit">
              <CoinBurst />
              <p class="animate-cha-ching font-display text-[5.5rem] leading-none font-semibold tracking-tight text-lamp portrait:text-[4.4rem]">
                {listing.price ? money(listing.price) : 'Listed!'}
              </p>
            </div>
            <p class="mt-3 font-mono text-lg text-night-soft">buyers nearby can see it now</p>
            <div class="mt-10 shrink-0 portrait:mt-auto portrait:pt-4"><ButtonHint label="press · done" /></div>
          {:else if screen === 'error'}
            <h2 class="font-display text-[3.4rem] leading-none font-semibold tracking-tight portrait:text-[2.4rem]">That didn't work.</h2>
            <p class="mt-6 line-clamp-3 max-w-[30rem] font-mono text-base text-night-soft">{problem}</p>
            <div class="mt-12 shrink-0 portrait:mt-auto portrait:pt-4"><ButtonHint pulse label="press to try again" /></div>
          {/if}
        </div>
      {/key}
    </div>
  {/if}

  {#if screen === 'thanks'}
    <section class="absolute inset-0 grid place-items-center text-center portrait:px-7" in:fade={{ duration: 900, delay: 1000 }}
      out:fade={{ duration: 500 }}>
      <div>
        <h2 class="font-display text-[7rem] leading-none font-semibold tracking-tight portrait:text-[4.2rem]">Thank you.</h2>
        <p class="mt-6 font-mono text-xl text-night-soft">{thanksLine}</p>
      </div>
      <div class="absolute bottom-14 left-16 portrait:bottom-10 portrait:left-7"><ButtonHint label="press for another" /></div>
      {#if config.site}
        <div class="absolute right-16 bottom-14 flex items-center gap-5 text-left portrait:right-7 portrait:bottom-24 portrait:flex-col portrait:items-end portrait:gap-2 portrait:text-right">
          <p class="font-mono text-base text-night-soft">need something?<br />ask here</p>
          <Qr text={config.site} class="size-28" />
        </div>
      {/if}
    </section>
  {/if}

  {#if screen !== 'attract'}
    <p class="pointer-events-none absolute right-0 bottom-4 left-0 text-center font-mono text-xs text-night-soft/60" transition:fade>
      press 3× quickly to start over
    </p>
  {/if}

  {#if flashing}
    <div class="pointer-events-none fixed inset-0 bg-cream" out:fade={{ duration: 650 }}></div>
  {/if}
</main>
