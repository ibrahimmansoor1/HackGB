<script>
  import { donateItem, listItem } from '$lib/api.js';
  import ListingInfo from '$lib/ListingInfo.svelte';
  import { takePendingPhoto } from '$lib/pending.js';

  // A photo picked on the landing page arrives here ready to go.
  let image = $state(takePendingPhoto());
  let preview = $state(null);
  let note = $state('');
  let zip = $state('');
  let loading = $state(false);
  let error = $state('');
  let item = $state(null);
  let listing = $state(null);
  let listingBusy = $state(false);
  let listingError = $state('');

  $effect(() => {
    if (!image) { preview = null; return; }
    const url = URL.createObjectURL(image);
    preview = url;
    return () => URL.revokeObjectURL(url);
  });

  async function submit() {
    if (!image && !note) { error = 'Add a photo or a short description.'; return; }
    if (!zip) { error = 'Add your zip code.'; return; }
    loading = true; error = ''; item = null; listing = null; listingError = '';
    try { item = await donateItem({ image, note, zip }); }
    catch (e) { error = e.message; }
    finally { loading = false; }
  }

  // Selling instead: list the saved item on Nostr (shows on Shopstr).
  async function sell() {
    listingBusy = true; listingError = '';
    try { ({ item, listing } = await listItem(item.id)); }
    catch (e) { listingError = e.message; }
    finally { listingBusy = false; }
  }
</script>

<h1>Give something</h1>

<label for="photo">Photo</label>
<input id="photo" type="file" accept="image/*" capture="environment"
  onchange={(e) => (image = e.currentTarget.files?.[0] ?? null)} />
{#if preview && !item}<img src={preview} alt="Preview of what you are giving" width="160" />{/if}

<label for="note">Anything we should know? (optional)</label>
<textarea id="note" rows="2" bind:value={note} placeholder="Barely worn, size M"></textarea>

<label for="zip">Zip code</label>
<input id="zip" bind:value={zip} inputmode="numeric" maxlength="5" />

<button onclick={submit} disabled={loading}>{loading ? 'Describing your item…' : 'Give item'}</button>

{#if error}<p role="alert">{error}</p>{/if}

{#if item}
  <h2>Saved: {item.color} {item.item}</h2>
  {#if item.image_url}<img src={item.image_url} alt={item.summary} width="240" />{/if}
  <p>{item.summary}</p>
  <p>{item.attributes.join(', ')} · {item.condition}{item.size ? ` · size ${item.size}` : ''}</p>

  {#if listing}
    <h2>For sale</h2>
    <ListingInfo {listing} />
    <p class="text-sm text-ink-soft">If it doesn't sell in 30 days, it goes back to the donation pool.
      See all listings on the <a class="underline" href="/marketplace">marketplace</a>.</p>
  {:else if item.status === 'available'}
    <p class="text-ink-soft">It's ready for someone nearby. Or sell it instead:</p>
    <button onclick={sell} disabled={listingBusy}>
      {listingBusy ? 'Listing on Shopstr…' : 'List on Shopstr'}
    </button>
    {#if listingError}<p role="alert">{listingError}</p>{/if}
  {/if}
{/if}
