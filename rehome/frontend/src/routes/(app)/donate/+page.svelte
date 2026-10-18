<script>
  import { parseItem, sellDraft, donateDraft, postDraft, handleDraft } from '$lib/api.js';
  import { takePendingPhoto } from '$lib/pending.js';
  import ListingInfo from '$lib/ListingInfo.svelte';

  // A photo picked on the landing page arrives here ready to go.
  const pending = takePendingPhoto();
  let images = $state(pending ? [pending] : []);
  let preview = $state(null);
  let text = $state('');
  let zip = $state('');
  let loading = $state('');
  let error = $state('');
  let draft = $state(null);
  let donated = $state(null);
  let quote = $state(null);
  let price = $state(null);
  let sold = $state(null);   // { item, listing } once it's listed
  let handled = $state(null);

  $effect(() => {
    if (!images.length) { preview = null; return; }
    const url = URL.createObjectURL(images[0]);
    preview = url;
    return () => URL.revokeObjectURL(url);
  });

  async function run(label, fn) {
    loading = label; error = '';
    try { await fn(); }
    catch (e) { error = e.message; }
    finally { loading = ''; }
  }

  function describe() {
    if (!images.length && !text) { error = 'Add a photo or a short description.'; return; }
    if (!zip) { error = 'Add your zip code.'; return; }
    draft = null; donated = null; quote = null; sold = null; handled = null;
    run('Describing your item…', async () => { draft = await parseItem({ images, text, zip }); });
  }

  function letAgentsHandle() {
    run('Our agents are on it…', async () => { handled = await handleDraft(draft.draft_id); });
  }

  function sell() {
    run('Checking prices…', async () => {
      quote = await sellDraft(draft.draft_id);
      const p = quote.suggested_price;
      price = Math.round((p.low + p.high) / 2);
    });
  }

  function list() {
    if (!(price > 0)) { error = 'Pick a price above $0.'; return; }
    run('Listing on Shopstr…', async () => { sold = await postDraft(draft.draft_id, price); });
  }

  function donate() {
    run('Donating…', async () => { donated = await donateDraft(draft.draft_id); });
  }

  function startOver() {
    draft = null; donated = null; quote = null; sold = null; price = null; handled = null;
    images = []; text = '';
  }
</script>

<h1>Give something</h1>

{#if !draft}
  <label for="photo">Photos</label>
  <input id="photo" type="file" accept="image/*" capture="environment" multiple
    onchange={(e) => (images = [...(e.currentTarget.files ?? [])])} />
  {#if preview}<img src={preview} alt="Preview of what you are giving" width="160" class="mt-2 rounded-lg" />{/if}

  <label for="text">Anything we should know? (optional)</label>
  <textarea id="text" rows="2" bind:value={text} placeholder="Barely worn, size M"></textarea>

  <label for="zip">Zip code</label>
  <input id="zip" bind:value={zip} inputmode="numeric" maxlength="5" />

  <button onclick={describe} disabled={!!loading}>{loading || 'Describe my item'}</button>
{:else}
  {@const it = draft.item}
  <h2>{it.color} {it.brand ? `${it.brand} ` : ''}{it.item}</h2>
  {#if draft.image_url}<img src={draft.image_url} alt={it.summary} width="240" class="rounded-lg" />{/if}
  <p>{it.summary}</p>
  <p>{it.attributes.join(', ')} · {it.condition}{it.size ? ` · size ${it.size}` : ''}</p>

  {#if handled}
    <p role="status">{handled.summary}</p>
    {#if handled.listing}<ListingInfo listing={handled.listing} />{/if}
    <button onclick={startOver}>Give something else</button>
  {:else if donated}
    <p role="status">{donated.message}</p>
    <button onclick={startOver}>Give something else</button>
  {:else if sold}
    <h2>For sale</h2>
    <ListingInfo listing={sold.listing} />
    <p class="text-sm text-ink-soft">If it doesn't sell in 30 days, it goes back to the donation pool.
      See all listings on the <a class="underline" href="/marketplace">marketplace</a>.</p>
    <button onclick={startOver}>Give something else</button>
  {:else}
    {#if !quote}
      <button onclick={letAgentsHandle} disabled={!!loading}>Let Rehome handle it</button>
      <p class="hint">Our agents price it, check who nearby needs it, then sell or donate it for you.</p>
    {/if}
    {#if quote}
      {@const p = quote.suggested_price}
      <h3>{quote.basis === 'active listings' ? 'Similar items are currently listed for' : 'Estimated value'}:
        ${p.low}–${p.high}</h3>
      {#if quote.comps.length}
        <ul>
          {#each quote.comps as c (c.url)}
            <li><a href={c.url} target="_blank" rel="noopener noreferrer">{c.title}</a> · ${c.price}{c.condition ? ` · ${c.condition}` : ''}</li>
          {/each}
        </ul>
      {/if}
      <p><strong>{quote.listing_draft.title}</strong><br />{quote.listing_draft.description}</p>

      <label for="price">Your price (USD)</label>
      <input id="price" type="number" min="1" step="1" bind:value={price} class="!w-32" />
      <button onclick={list} disabled={!!loading}>List on Shopstr</button>
      <p class="text-sm text-ink-soft">Not worth the hassle? You can still donate it.</p>
    {:else}
      <button onclick={sell} disabled={!!loading}>Sell it</button>
    {/if}
    <button onclick={donate} disabled={!!loading}>Donate it</button>
    <button onclick={startOver} disabled={!!loading}>Start over</button>
    {#if loading}<p role="status">{loading}</p>{/if}
  {/if}
{/if}

{#if error}<p role="alert">{error}</p>{/if}

<style>
  .hint { color: #666; margin-top: 0.25rem; }
</style>
