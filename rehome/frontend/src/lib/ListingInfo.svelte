<script>
  // Price, status and links for one marketplace listing (GET /api/listings shape).
  let { listing } = $props();

  const relays = $derived(listing.relays_accepted?.length ?? 0);
</script>

<div class="flex flex-wrap items-center gap-x-3 gap-y-2">
  <span class="font-display text-2xl font-bold">${listing.price}</span>
  {#if listing.status === 'expired'}
    <span class="rounded-full bg-ink/10 px-2.5 py-0.5 text-xs font-semibold text-ink-soft">
      Expired · back in the donation pool
    </span>
  {:else if listing.dry_run}
    <span class="rounded-full bg-lamp/20 px-2.5 py-0.5 text-xs font-semibold text-lamp-ink">
      Practice run · not published
    </span>
  {:else}
    <span class="rounded-full bg-sage/15 px-2.5 py-0.5 text-xs font-semibold text-sage">
      Live on Nostr · {relays} relay{relays === 1 ? '' : 's'}
    </span>
  {/if}
</div>

{#if !listing.dry_run}
  <p class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm font-semibold">
    <a class="underline underline-offset-4" href={listing.nostr_url} target="_blank" rel="noopener">
      View listing ↗
    </a>
    <a class="underline underline-offset-4" href={listing.url} target="_blank" rel="noopener">
      Open on Shopstr ↗
    </a>
  </p>
{/if}
