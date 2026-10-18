<script>
  // Placeholder styling. Frontend owner: replace freely; keep api.js as the only backend caller.
  let { children } = $props();
</script>

<header>
  <a href="/" class="brand">Rehome</a>
  <nav>
    <a href="/donate">Give something</a>
    <a href="/request">Find something</a>
    <a href="/feed">Agent activity</a>
  </nav>
</header>

<main>{@render children()}</main>

<style>
  :global(body) { font-family: system-ui, sans-serif; margin: 0; line-height: 1.5; }
  header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.5rem; border-bottom: 1px solid #ddd; }
  nav { display: flex; gap: 1.25rem; }
  a { color: inherit; }
  .brand { font-weight: 700; text-decoration: none; }
  main { max-width: 44rem; margin: 2rem auto; padding: 0 1.5rem; }
  :global(label) { display: block; margin: 1rem 0 0.25rem; font-weight: 600; }
  :global(input), :global(textarea) { width: 100%; padding: 0.5rem; font: inherit; box-sizing: border-box; }
  :global(button) { margin-top: 1.25rem; padding: 0.6rem 1.2rem; font: inherit; cursor: pointer; }
  :global(:focus-visible) { outline: 2px solid #1f7a6d; outline-offset: 2px; }
</style>
