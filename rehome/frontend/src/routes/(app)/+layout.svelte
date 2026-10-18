<script>
  // Shared shell for the task pages (give, get help, feed).
  // The scoped form styles are placeholders until each page gets its Tailwind redesign.
  let { children } = $props();
</script>

<main class="app mx-auto max-w-2xl px-4 py-8 sm:px-6">{@render children()}</main>

<style>
  .app :global(h1) { font-family: 'Bricolage Grotesque Variable', sans-serif; font-size: 2rem; font-weight: 700; margin-bottom: 1rem; }
  .app :global(h2) { font-family: 'Bricolage Grotesque Variable', sans-serif; font-size: 1.35rem; font-weight: 600; margin: 1.5rem 0 0.5rem; }
  .app :global(p) { margin: 0.75rem 0; }
  .app :global(ol) { list-style: decimal; padding-left: 1.25rem; }
  .app :global(label) { display: block; margin: 1rem 0 0.25rem; font-weight: 600; }
  .app :global(input:not([type='file'])), .app :global(textarea) {
    width: 100%; padding: 0.5rem 0.75rem; font: inherit; border: 1px solid var(--line);
    border-radius: 0.6rem; background: var(--surface);
  }
  .app :global(button) {
    margin-top: 1.25rem; padding: 0.6rem 1.2rem; font: inherit; font-weight: 600; cursor: pointer;
    border-radius: 999px; background: var(--ink); color: var(--ground);
  }
  .app :global(button:disabled) { opacity: 0.6; cursor: progress; }
</style>
