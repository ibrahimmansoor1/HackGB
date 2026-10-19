import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';

// `npm run dev` forwards the hardware and backend routes to a running server.py: the Pi by
// default, or e.g. KIOSK_SERVER=http://localhost:8091 for one started with --fake.
const target = process.env.KIOSK_SERVER || 'http://hackpi.local:8080';
const proxy = Object.fromEntries(
  ['/hw', '/api', '/static', '/config.json'].map((path) => [path, { target, changeOrigin: true }])
);

export default defineConfig({
  plugins: [tailwindcss(), svelte()],
  server: { proxy }
});
