<script>
  import { renderSVG } from 'uqr';

  let { text, class: className = '' } = $props();

  const svg = $derived(renderSVG(text, { border: 2, whiteColor: '#f6efe3', blackColor: '#1d1522' }));
</script>

<div class={['overflow-hidden rounded-xl [&>svg]:block [&>svg]:size-full', className]}>{@html svg}</div>
