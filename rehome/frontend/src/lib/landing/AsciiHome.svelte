<script>
  // Mounts the three.js ASCII scene. three.js is imported on the client only,
  // so it never runs during SSR and stays out of the other pages' bundles.
  import { onMount } from 'svelte';

  let { class: className = '' } = $props();

  let host;
  let scene = null;
  let failed = $state(false);

  // Shown if WebGL is unavailable.
  const FALLBACK = String.raw`
                 (  )
               (    )
                 ||
       __________||_________
      /                     \
     /_______________________\
      |  [##]    __    [##] |
      |  [##]   |  |   [##] |
  ~~~~|_________|__|________|~~~~`;

  onMount(() => {
    let alive = true;
    import('./ascii-home.js')
      .then(({ createAsciiHome }) => createAsciiHome(host))
      .then((s) => {
        if (alive) scene = s;
        else s.destroy();
      })
      .catch((e) => {
        console.warn('ASCII hero disabled:', e);
        failed = true;
      });
    return () => {
      alive = false;
      scene?.destroy();
    };
  });

  /** @param {'give' | 'help'} kind */
  export function launch(kind) {
    scene?.launch(kind);
  }
</script>

<div bind:this={host} class="relative size-full {className}" aria-hidden="true">
  {#if failed}
    <pre class="grid size-full place-items-center font-mono text-xs leading-tight text-lamp sm:text-sm">{FALLBACK}</pre>
  {/if}
</div>
