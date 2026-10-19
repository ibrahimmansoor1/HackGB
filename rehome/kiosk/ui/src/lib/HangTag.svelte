<script>
  // The parsed item as a thrift-store hang tag, like the landing page's ItemTag (the photo is
  // on the print next to it, so the tag carries only the words).
  import Shirt from '@lucide/svelte/icons/shirt';
  import Footprints from '@lucide/svelte/icons/footprints';
  import Glasses from '@lucide/svelte/icons/glasses';
  import Sofa from '@lucide/svelte/icons/sofa';
  import Plug from '@lucide/svelte/icons/plug';
  import Baby from '@lucide/svelte/icons/baby';
  import Package from '@lucide/svelte/icons/package';

  let { item, tilt = 2 } = $props();

  const ICONS = { outerwear: Shirt, tops: Shirt, bottoms: Shirt, footwear: Footprints,
    accessories: Glasses, home: Sofa, electronics: Plug, kids: Baby };

  const Icon = $derived(ICONS[item.category] ?? Package);
  const details = $derived(
    [item.color, item.size && `size ${item.size}`, item.condition].filter(Boolean).join(' · ')
  );
</script>

<div class="w-[26rem] portrait:w-[25.5rem] drop-shadow-[0_1.4rem_1.2rem_rgb(0_0_0/0.45)]" style:rotate="{tilt}deg">
  <article class="tag relative bg-kraft px-7 pt-14 pb-7 text-night portrait:px-6 portrait:pt-11 portrait:pb-5">
    <span class="absolute top-5 left-1/2 size-4 -translate-x-1/2 rounded-full bg-night ring-2 ring-night/20"
      aria-hidden="true"></span>
    <div class="flex items-start gap-4">
      <Icon class="mt-1.5 size-8 shrink-0 opacity-55" strokeWidth={1.5} />
      <div class="min-w-0">
        {#if item.brand}
          <p class="truncate font-mono text-sm tracking-[0.2em] text-night/60 uppercase">{item.brand}</p>
        {/if}
        <h3 class="line-clamp-2 font-mono text-[1.9rem] leading-tight font-medium capitalize portrait:text-[1.6rem]">{item.item}</h3>
        <p class="mt-2 line-clamp-2 font-mono text-base text-night/70">{details}</p>
      </div>
    </div>
    {#if item.attributes?.length}
      <ul class="mt-5 flex flex-wrap gap-2 portrait:mt-4 portrait:max-h-[2.15rem] portrait:overflow-hidden">
        {#each item.attributes.slice(0, 5) as attribute}
          <li class="rounded-full border border-night/25 px-3 py-1 font-mono text-sm">{attribute}</li>
        {/each}
      </ul>
    {/if}
  </article>
</div>

<style>
  .tag {
    clip-path: polygon(14% 0, 86% 0, 100% 9%, 100% 100%, 0 100%, 0 9%);
  }
</style>
