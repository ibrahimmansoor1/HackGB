<script>
  import { page } from '$app/state';
  import { requestItem, acceptMatch } from '$lib/api.js';

  // The landing page passes what you typed as ?q=
  let text = $state(page.url.searchParams.get('q') ?? '');
  let zip = $state('');
  let loading = $state(false);
  let error = $state('');
  let result = $state(null);
  let claiming = $state('');
  let claimed = $state(null);

  async function submit() {
    if (!text || !zip) { error = 'Describe what you need and add your zip code.'; return; }
    loading = true; error = ''; result = null; claimed = null;
    try { result = await requestItem({ text, zip }); }
    catch (e) { error = e.message; }
    finally { loading = false; }
  }

  async function claim(m) {
    claiming = m.item_id; error = '';
    try { claimed = { ...(await acceptMatch(result.request_id, m.item_id)), title: m.title }; }
    catch (e) { error = e.message; }
    finally { claiming = ''; }
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

{#if claimed}
  <h2>It’s yours: {claimed.title}</h2>
  <p role="status">{claimed.handoff.message}</p>
{:else if result}
  {#if result.query.inferred_context.length}
    <p>We took into account: {result.query.inferred_context.join(', ')}.</p>
  {/if}
  {#if result.matches.length}
    <h2>Matches</h2>
    <ol>
      {#each result.matches as m (m.item_id)}
        <li class="mb-3 list-none">
          <div class="flex items-start gap-3">
            <span class="w-5 shrink-0 pt-0.5 font-mono text-sm text-ink-soft">{m.rank}.</span>
            {#if m.item.image_url}
              <img src={m.item.image_url} alt="" loading="lazy"
                class="size-14 shrink-0 rounded-lg border border-line object-cover" />
            {/if}
            <div>
              <strong>{m.item.color} {m.title}</strong>{m.item.size ? `, size ${m.item.size}` : ''}
              <br />{m.reason}
              <br /><button class="!mt-2" onclick={() => claim(m)} disabled={!!claiming}>
                {claiming === m.item_id ? 'Claiming…' : 'Claim this'}
              </button>
            </div>
          </div>
        </li>
      {/each}
    </ol>
  {:else}
    <p>No good match yet. Your request stays open, and we’ll match it when something fits.</p>
  {/if}
{/if}
