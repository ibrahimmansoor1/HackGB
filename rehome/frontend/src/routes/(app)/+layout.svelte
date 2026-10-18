<script>
  // Shared shell for the task pages (give, get help, feed, marketplace).
  // Pages set their own width. The old scaffold form styles below only apply
  // inside .legacy, for pages that haven't had their Tailwind redesign yet.
  let { children } = $props();
</script>

<main class="app mx-auto max-w-6xl px-4 py-8 sm:px-6">{@render children()}</main>

<style>
  .app :global(.legacy) { max-width: 42rem; margin-inline: auto; }
  .app :global(.legacy h1) { font-family: 'Bricolage Grotesque Variable', sans-serif; font-size: 2rem; font-weight: 700; margin-bottom: 1rem; }
  .app :global(.legacy h2) { font-family: 'Bricolage Grotesque Variable', sans-serif; font-size: 1.35rem; font-weight: 600; margin: 1.5rem 0 0.5rem; }
  .app :global(.legacy p) { margin: 0.75rem 0; }
  .app :global(.legacy ol) { list-style: decimal; padding-left: 1.25rem; }
  .app :global(.legacy label) { display: block; margin: 1rem 0 0.25rem; font-weight: 600; }
  .app :global(.legacy input:not([type='file'])), .app :global(.legacy textarea) {
    width: 100%; padding: 0.5rem 0.75rem; font: inherit; border: 1px solid var(--line);
    border-radius: 0.6rem; background: var(--surface);
  }
  .app :global(.legacy button) {
    margin-top: 1.25rem; padding: 0.6rem 1.2rem; font: inherit; font-weight: 600; cursor: pointer;
    border-radius: 999px; background: var(--ink); color: var(--ground);
  }
  .app :global(.legacy button) { margin-right: 0.35rem; transition: background-color 300ms ease-out, filter 300ms ease-out; }
  .app :global(.legacy button.primary) { background: var(--lamp); color: #1d1522; }
  .app :global(.legacy button.primary:hover) { filter: brightness(1.06); }
  .app :global(.legacy button.secondary) { background: transparent; color: var(--ink); box-shadow: inset 0 0 0 1px var(--line); }
  .app :global(.legacy button.secondary:hover) { background: color-mix(in oklab, var(--ink) 5%, transparent); }
  .app :global(.legacy button.ghost) { background: transparent; color: var(--ink-soft); padding-inline: 0.6rem; }
  .app :global(.legacy button.ghost:hover) { color: var(--ink); }
  .app :global(.legacy button:disabled) { opacity: 0.6; cursor: progress; }
</style>
