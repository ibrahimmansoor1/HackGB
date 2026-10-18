<script>
  import { parseItem, donateDraft } from '$lib/api.js';

  let images = $state([]);
  let text = $state('');
  let zip = $state('');
  let loading = $state('');
  let error = $state('');
  let draft = $state(null);
  let donated = $state(null);

  async function run(label, fn) {
    loading = label; error = '';
    try { await fn(); }
    catch (e) { error = e.message; }
    finally { loading = ''; }
  }

  function describe() {
    if (!images.length && !text) { error = 'Add a photo or a short description.'; return; }
    if (!zip) { error = 'Add your zip code.'; return; }
    draft = null; donated = null;
    run('Describing your item…', async () => { draft = await parseItem({ images, text, zip }); });
  }

  function donate() {
    run('Donating…', async () => { donated = await donateDraft(draft.draft_id); });
  }

  function startOver() {
    draft = null; donated = null; images = []; text = '';
  }
</script>

<h1>Give something</h1>

{#if !draft}
  <label for="photo">Photos</label>
  <input id="photo" type="file" accept="image/*" capture="environment" multiple
    onchange={(e) => (images = [...(e.currentTarget.files ?? [])])} />

  <label for="text">Anything we should know? (optional)</label>
  <textarea id="text" rows="2" bind:value={text} placeholder="Barely worn, size M"></textarea>

  <label for="zip">Zip code</label>
  <input id="zip" bind:value={zip} inputmode="numeric" maxlength="5" />

  <button onclick={describe} disabled={!!loading}>{loading || 'Describe my item'}</button>
{:else}
  {@const it = draft.item}
  <h2>{it.color} {it.brand ? `${it.brand} ` : ''}{it.item}</h2>
  {#if draft.image_url}<img src={draft.image_url} alt={it.summary} width="240" />{/if}
  <p>{it.summary}</p>
  <p>{it.attributes.join(', ')} · {it.condition}{it.size ? ` · size ${it.size}` : ''}</p>

  {#if donated}
    <p role="status">{donated.message}</p>
    <button onclick={startOver}>Give something else</button>
  {:else}
    <button onclick={donate} disabled={!!loading}>{loading || 'Donate it'}</button>
    <button onclick={startOver} disabled={!!loading}>Start over</button>
  {/if}
{/if}

{#if error}<p role="alert">{error}</p>{/if}
