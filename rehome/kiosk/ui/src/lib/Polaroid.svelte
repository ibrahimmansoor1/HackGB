<script>
  // The captured photo as an instant print. It develops once, when it first appears.
  let { src, caption = '', tilt = -3 } = $props();
</script>

<figure class="m-0 w-[34rem] bg-cream portrait:w-[20rem] p-[1.1rem] pb-0 shadow-[0_2.5rem_3rem_-1rem_rgb(0_0_0/0.6)]"
  style:rotate="{tilt}deg">
  <div class="aspect-video overflow-hidden bg-night-deep">
    <img {src} alt="" class="size-full animate-develop object-cover" />
  </div>
  <figcaption class="h-[4.6rem] truncate px-4 text-center leading-[4.6rem] portrait:h-[3.4rem] portrait:leading-[3.4rem] font-mono text-xl text-night/75 capitalize">
    {caption}
  </figcaption>
</figure>
