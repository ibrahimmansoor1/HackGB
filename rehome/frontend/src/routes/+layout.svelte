<script>
  // Fonts are bundled (not loaded from Google) so the demo works on bad venue wifi.
  import '../app.css';
  import '@fontsource-variable/bricolage-grotesque/opsz.css';
  import '@fontsource-variable/figtree';
  import '@fontsource/dm-mono/400.css';
  import '@fontsource/dm-mono/500.css';
  import SiteHeader from '$lib/components/SiteHeader.svelte';

  let { children } = $props();
</script>

<svelte:head>
  <title>ReHome</title>
  <meta name="description" content="Give away what you don't use with one photo, or ask for what you need in one sentence." />
</svelte:head>

<SiteHeader />
{@render children()}
