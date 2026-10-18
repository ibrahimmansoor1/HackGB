<script>
  // A number that counts up slowly when it changes.
  import { tweened } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import { reduced } from '$lib/motion.js';

  let { value = 0 } = $props();

  const shown = tweened(0, { duration: reduced() ? 0 : 900, easing: cubicOut });
  $effect(() => { shown.set(value); });
</script>

{Math.round($shown)}
