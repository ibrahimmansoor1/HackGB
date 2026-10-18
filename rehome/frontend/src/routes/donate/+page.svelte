<script>
  import { donateItem, BASE } from '$lib/api.js';

  let image = $state(null);
  let note = $state('');
  let zip = $state('');
  let loading = $state(false);
  let error = $state('');
  let item = $state(null);

  async function submit() {
    if (!image && !note) { error = 'Add a photo or a short description.'; return; }
    if (!zip) { error = 'Add your zip code.'; return; }
    loading = true; error = ''; item = null;
    try { item = await donateItem({ image, note, zip }); }
    catch (e) { error = e.message; }
    finally { loading = false; }
  }
</script>

<h1>Give something</h1>

<label for="photo">Photo</label>
<input id="photo" type="file" accept="image/*" capture="environment"
  onchange={(e) => (image = e.currentTarget.files?.[0] ?? null)} />

<label for="note">Anything we should know? (optional)</label>
<textarea id="note" rows="2" bind:value={note} placeholder="Barely worn, size M"></textarea>

<label for="zip">Zip code</label>
<input id="zip" bind:value={zip} inputmode="numeric" maxlength="5" />

<button onclick={submit} disabled={loading}>{loading ? 'Describing your item…' : 'Give item'}</button>

{#if error}<p role="alert">{error}</p>{/if}

{#if item}
  <h2>Listed: {item.color} {item.item}</h2>
  {#if item.image_url}<img src={BASE + item.image_url} alt={item.summary} width="240" />{/if}
  <p>{item.summary}</p>
  <p>{item.attributes.join(', ')} · {item.condition}{item.size ? ` · size ${item.size}` : ''}</p>
{/if}
