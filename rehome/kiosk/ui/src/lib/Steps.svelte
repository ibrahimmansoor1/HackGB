<script>
  // The agents' activity (GET /api/events) as it streams in while the backend works.
  // The newest step's dot glows; earlier ones settle to grey.
  import { fly } from 'svelte/transition';
  import { flip } from 'svelte/animate';
  import { cubicOut } from 'svelte/easing';

  let { steps } = $props();

  const shown = $derived(steps.slice(-4));
</script>

<ol class="mt-8 space-y-3 font-mono text-lg portrait:mt-5 portrait:text-base">
  {#each shown as step, i (step.id)}
    <li class="flex items-baseline gap-4" in:fly={{ y: 14, duration: 800, easing: cubicOut }}
      animate:flip={{ duration: 700, easing: cubicOut }}>
      <span class={['size-2.5 shrink-0 -translate-y-0.5 rounded-full transition-colors duration-700',
        i === shown.length - 1 ? 'animate-breathe bg-lamp' : 'bg-night-soft/35']}></span>
      <span class="w-36 shrink-0 text-night-soft portrait:w-28">{step.agent}</span>
      <span class="min-w-0 text-night-ink">{step.message}</span>
    </li>
  {/each}
</ol>
