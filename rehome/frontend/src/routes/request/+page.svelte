<script>
  import { requestItem } from '$lib/api.js';

  let text = $state('');
  let zip = $state('');
  let loading = $state(false);
  let error = $state('');
  let result = $state(null);

  async function submit() {
    if (!text || !zip) { error = 'Describe what you need and add your zip code.'; return; }
    loading = true; error = ''; result = null;
    try { result = await requestItem({ text, zip }); }
    catch (e) { error = e.message; }
    finally { loading = false; }
  }
</script>

<h1>Find something</h1>

<label for="need">What do you need?</label>
<textarea id="need" rows="2" bind:value={text}
  placeholder="A warm coat, I’m moving to Chicago in December"></textarea>

<label for="zip">Zip code</label>
<input id="zip" bind:value={zip} inputmode="numeric" maxlength="5" />

<button onclick={submit} disabled={loading}>{loading ? 'Searching…' : 'Find matches'}</button>

{#if error}<p role="alert">{error}</p>{/if}

{#if result}
  {#if result.query.inferred_context.length}
    <p>We took into account: {result.query.inferred_context.join(', ')}.</p>
  {/if}
  {#if result.matches.length}
    <h2>Matches</h2>
    <ol>
      {#each result.matches as m (m.item_id)}
        <li>
          <strong>{m.item.color} {m.item.item}</strong>{m.item.size ? `, size ${m.item.size}` : ''}
          <br />{m.reason}
        </li>
      {/each}
    </ol>
  {:else}
    <p>No good match yet. Your request stays open, and we’ll match it when something fits.</p>
  {/if}
{/if}
