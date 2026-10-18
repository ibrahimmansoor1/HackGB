<script>
  // An item's photo. The demo inventory's seed images are text placeholders,
  // so for those (and items with no photo) draw a card: a category icon on the
  // item's own color.
  import Shirt from '@lucide/svelte/icons/shirt';
  import Footprints from '@lucide/svelte/icons/footprints';
  import LampDesk from '@lucide/svelte/icons/lamp-desk';
  import Heater from '@lucide/svelte/icons/heater';
  import CookingPot from '@lucide/svelte/icons/cooking-pot';
  import Bed from '@lucide/svelte/icons/bed';
  import Hand from '@lucide/svelte/icons/hand';
  import Snowflake from '@lucide/svelte/icons/snowflake';
  import Umbrella from '@lucide/svelte/icons/umbrella';
  import Baby from '@lucide/svelte/icons/baby';
  import Package from '@lucide/svelte/icons/package';

  let { item, class: cls = '' } = $props();

  const COLORS = {
    black: '#3a3040', olive: '#6b7a3a', navy: '#2c4370', yellow: '#d9a62c', brown: '#7a5233',
    gray: '#8a8790', grey: '#8a8790', tan: '#b88f5e', red: '#b4553a', green: '#557452',
    white: '#cfc6b8', blue: '#3f6fb0', pink: '#d77fa1', beige: '#c9b28c', silver: '#9da2a8',
    orange: '#d9792c', purple: '#7a5a9a'
  };

  const ICONS = [
    [/lamp/, LampDesk], [/heater/, Heater], [/cookware|\bpot\b|\bpan\b/, CookingPot], [/blanket|bed/, Bed],
    [/glove|mitten/, Hand], [/beanie|hat|scarf/, Snowflake], [/boot|shoe|sneaker/, Footprints],
    [/rain/, Umbrella]
  ];
  const BY_CATEGORY = { kids: Baby, footwear: Footprints, outerwear: Shirt, tops: Shirt, bottoms: Shirt, home: Package };

  const real = $derived(!!item.image_url && !item.image_url.includes('/static/seed/'));
  const tint = $derived(COLORS[item.color?.toLowerCase()] ?? '#b88f5e');
  const Icon = $derived(
    ICONS.find(([re]) => re.test(item.item ?? ''))?.[1] ?? BY_CATEGORY[item.category] ?? Package
  );
</script>

{#if real}
  <img src={item.image_url} alt={item.summary ?? item.item} loading="lazy"
    class="size-full object-cover {cls}" />
{:else}
  <div class="relative grid size-full place-items-center {cls}"
    style="background: color-mix(in oklab, {tint} 24%, var(--surface));" role="img"
    aria-label={item.summary ?? item.item}>
    <Icon class="size-1/3" strokeWidth={1.25}
      style="color: color-mix(in oklab, {tint} 80%, var(--ink));" />
    <span class="absolute bottom-2.5 left-3 font-mono text-[0.7rem] tracking-wide text-ink-soft">
      {item.color} · {item.category}
    </span>
  </div>
{/if}
