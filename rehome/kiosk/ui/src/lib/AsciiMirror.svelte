<script>
  // The webcam drawn as colored ASCII and mirrored like a looking glass: the attract screen,
  // and a dim backdrop behind the others. Frames come from a hidden <img> of the MJPEG stream.
  //
  // Each frame: the picture is shrunk to one pixel per character cell. Brightness picks the
  // character, drawn one text row at a time in white; then the cell colors (saturation boosted)
  // are painted over the glyphs with `source-in`, so every character takes its spot's color.
  import { onMount } from 'svelte';

  let { opacity = 0.5, fps = 10 } = $props();

  const RAMP = ' .:-=+*#%@';
  const FONT = '"DM Mono", monospace';
  const STREAM = `/hw/stream.mjpg?fps=${fps}`;

  let img, canvas;

  onMount(() => {
    const out = canvas.getContext('2d');
    const small = document.createElement('canvas');
    const sctx = small.getContext('2d', { willReadFrequently: true });
    const tint = document.createElement('canvas');
    const tctx = tint.getContext('2d');
    let cols, rows, cellW, fontPx, W, H, lum, colors;
    let lo = 0, hi = 255, lastSum = -1, staleSince = performance.now();

    // Cells as small as is still legible: 80 columns on the Pi's 480px portrait screen, 160 wide
    function layout() {
      const dpr = Math.min(2, devicePixelRatio || 1);
      W = canvas.width = Math.round(innerWidth * dpr);
      H = canvas.height = Math.round(innerHeight * dpr);
      cols = innerWidth >= innerHeight ? 160 : 80;
      cellW = W / cols;
      out.font = `500 100px ${FONT}`;
      fontPx = (cellW / out.measureText('0').width) * 100; // glyph advance == cell width exactly
      rows = Math.ceil(H / fontPx);
      small.width = tint.width = cols;
      small.height = tint.height = rows;
      lum = new Float32Array(cols * rows);
      colors = tctx.createImageData(cols, rows);
    }

    function draw() {
      if (!img.complete || !img.naturalWidth) return;
      // Crop the camera picture to the grid's shape (like object-fit: cover), mirrored
      const iw = img.naturalWidth, ih = img.naturalHeight, shape = (cols * cellW) / (rows * fontPx);
      const sw = Math.min(iw, ih * shape), sh = Math.min(ih, iw / shape);
      sctx.setTransform(-1, 0, 0, 1, cols, 0);
      sctx.drawImage(img, (iw - sw) / 2, (ih - sh) / 2, sw, sh, 0, 0, cols, rows);
      const px = sctx.getImageData(0, 0, cols, rows).data;
      const c = colors.data;
      let min = 255, max = 0, sum = 0;
      for (let i = 0, j = 0; i < lum.length; i++, j += 4) {
        const r = px[j], g = px[j + 1], b = px[j + 2];
        const l = 0.299 * r + 0.587 * g + 0.114 * b;
        lum[i] = l;
        sum += l;
        if (l < min) min = l;
        if (l > max) max = l;
        // Richer, brighter color than the webcam gives, so it reads on a dark screen
        c[j] = Math.min(255, (l + (r - l) * 1.9) * 1.35 + 30);
        c[j + 1] = Math.min(255, (l + (g - l) * 1.9) * 1.35 + 30);
        c[j + 2] = Math.min(255, (l + (b - l) * 1.9) * 1.35 + 30);
        c[j + 3] = 255;
      }
      // The stream ends when the camera stalls; reconnect once frames stop changing
      if (sum !== lastSum) (lastSum = sum), (staleSince = performance.now());
      else if (performance.now() - staleSince > 6000) {
        img.src = `${STREAM}&r=${Date.now()}`;
        staleSince = performance.now();
      }
      // Stretch the contrast to this scene, eased so the picture doesn't flicker
      lo += (min - lo) * 0.15;
      hi += (Math.max(max, lo + 48) - hi) * 0.15;

      out.globalCompositeOperation = 'source-over';
      out.clearRect(0, 0, W, H);
      out.fillStyle = '#fff';
      out.font = `500 ${fontPx}px ${FONT}`;
      out.textBaseline = 'top';
      for (let r = 0; r < rows; r++) {
        let line = '';
        for (let col = 0; col < cols; col++) {
          const v = Math.max(0, (lum[r * cols + col] - lo) / (hi - lo)) ** 0.75; // lift the midtones
          line += RAMP[Math.min(RAMP.length - 1, Math.round(v * (RAMP.length - 1)))];
        }
        out.fillText(line, 0, r * fontPx);
      }
      tctx.putImageData(colors, 0, 0);
      out.globalCompositeOperation = 'source-in';
      out.imageSmoothingEnabled = false;
      out.drawImage(tint, 0, 0, cols * cellW, rows * fontPx);
    }

    let timer;
    document.fonts.load(`500 16px ${FONT}`).finally(() => {
      layout();
      timer = setInterval(draw, 1000 / fps);
    });
    addEventListener('resize', layout);
    return () => {
      clearInterval(timer);
      removeEventListener('resize', layout);
    };
  });
</script>

<img bind:this={img} src={STREAM} alt="" class="pointer-events-none fixed top-0 left-0 size-px opacity-0" />
<canvas bind:this={canvas} class="pointer-events-none fixed inset-0 size-full transition-opacity duration-[1600ms] ease-out"
  style:opacity aria-hidden="true"></canvas>
