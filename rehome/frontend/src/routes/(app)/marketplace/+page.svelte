<script>
  // Items listed for sale on Nostr (shown on Shopstr). Unsold after 30 days,
  // they go back to the donation pool.
  import { onMount } from 'svelte';
  import { getListings, simulateExpiry } from '$lib/api.js';
  import ItemTag from '$lib/landing/ItemTag.svelte';
  import ListingInfo from '$lib/ListingInfo.svelte';

  let listings = $state([]);
  let loaded = $state(false);
  let busy = $state(false);
  let error = $state('');
  let notice = $state('');

  const active = $derived(listings.filter((l) => l.status === 'active'));

  async function load() {
    try { listings = (await getListings()).listings; error = ''; }
    catch (e) { error = e.message; }
    finally { loaded = true; }
  }

  async function expire() {
    busy = true; notice = '';
    try {
      const { expired } = await simulateExpiry();
      notice = expired.length
        ? `${expired.length} unsold item${expired.length === 1 ? '' : 's'} moved back to the donation pool.`
        : 'Nothing was listed.';
      await load();
    } catch (e) { error = e.message; }
    finally { busy = false; }
  }

  onMount(load);
</script>

<h1>Marketplace</h1>
<p class="text-ink-soft">Things people chose to sell, listed on Nostr so they show up on Shopstr.
  Whatever doesn't sell in 30 days is given away for free.</p>

{#if error}<p role="alert">{error}</p>{/if}

{#if loaded && !listings.length && !error}
  <p>Nothing listed yet. <a class="underline" href="/donate">Give something</a>, then choose
    “List on Shopstr”.</p>
{/if}

<div class="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-2">
  {#each listings as listing (listing.id)}
    <div class:opacity-60={listing.status === 'expired'}>
      <ItemTag item={listing.item} />
      {#if listing.title}
        <p class="mt-3 font-semibold">{listing.title}</p>
        <p class="text-sm text-ink-soft">{listing.description}</p>
      {/if}
      <div class="mt-3"><ListingInfo {listing} /></div>
    </div>
  {/each}
</div>

{#if active.length}
  <button onclick={expire} disabled={busy}>
    {busy ? 'Fast-forwarding…' : 'Simulate 30 days unsold'}
  </button>
{/if}
{#if notice}<p>{notice}</p>{/if}
