<script>
  // An inventory item drawn as a thrift-store hang tag.
  import Shirt from '@lucide/svelte/icons/shirt';
  import Footprints from '@lucide/svelte/icons/footprints';
  import Glasses from '@lucide/svelte/icons/glasses';
  import Sofa from '@lucide/svelte/icons/sofa';
  import Plug from '@lucide/svelte/icons/plug';
  import Baby from '@lucide/svelte/icons/baby';
  import Package from '@lucide/svelte/icons/package';
  import { mediaUrl } from '$lib/api.js';

  let { item, tilt = 0 } = $props();

  const ICONS = { outerwear: Shirt, tops: Shirt, bottoms: Shirt, footwear: Footprints,
    accessories: Glasses, home: Sofa, electronics: Plug, kids: Baby };

  const Icon = $derived(ICONS[item.category] ?? Package);
  const details = $derived(
    [item.color, item.size && `size ${item.size}`, item.condition].filter(Boolean).join(' · ')
  );
</script>

<div class="drop-shadow-[0_12px_14px_rgb(42_33_48/0.18)] transition-transform duration-300 hover:-translate-y-1"
  style:rotate="{tilt}deg">
  <article class="tag relative bg-kraft p-3 pt-9 text-night">
    <span class="absolute top-3.5 left-1/2 size-3 -translate-x-1/2 rounded-full bg-ground ring-2 ring-night/15"
      aria-hidden="true"></span>
    {#if item.image_url}
      <img src={mediaUrl(item.image_url)} alt="" loading="lazy" class="aspect-square w-full rounded-md bg-white/50 object-cover" />
    {:else}
      <div class="grid aspect-square w-full place-items-center rounded-md bg-white/35">
        <Icon class="size-10 opacity-55" strokeWidth={1.5} />
      </div>
    {/if}
    <h3 class="mt-3 font-mono text-[0.95rem] leading-tight font-medium capitalize">{item.item}</h3>
    <p class="mt-1 font-mono text-xs text-night/70">{details}</p>
  </article>
</div>

<style>
  .tag {
    clip-path: polygon(18% 0, 82% 0, 100% 8%, 100% 100%, 0 100%, 0 8%);
    border-radius: 0 0 0.6rem 0.6rem;
  }
</style>
