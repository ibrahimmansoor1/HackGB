<script>
  // Full-screen demo view for the second laptop at the expo table.
  import ActivityFeed from '$lib/ActivityFeed.svelte';
  import ImpactStats from '$lib/ImpactStats.svelte';
</script>

<div class="grid gap-10 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
  <div>
    <h1 class="font-display text-4xl font-bold tracking-tight">Impact</h1>
    <div class="mt-6"><ImpactStats /></div>
  </div>
  <div>
    <h2 class="flex items-center gap-2.5 font-display text-4xl font-bold tracking-tight">
      Agent activity
      <span class="relative flex size-2.5">
        <span class="absolute inline-flex size-full animate-ping rounded-full bg-sage opacity-60 [animation-duration:2s]"></span>
        <span class="relative inline-flex size-2.5 rounded-full bg-sage"></span>
      </span>
    </h2>
    <div class="mt-4"><ActivityFeed /></div>
  </div>
</div>
