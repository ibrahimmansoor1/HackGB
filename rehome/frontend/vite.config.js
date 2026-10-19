import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, loadEnv } from 'vite';

// Listen on the LAN and forward backend paths to the backend on this laptop, so
// other devices only need http://<this laptop's IP>:5173 (same origin, no CORS).
// REHOME_BACKEND (in .env) picks which backend, like the kiosk's setting of the same name.
// 127.0.0.1, not localhost: uvicorn binds IPv4 and Node may try ::1 first.
export default defineConfig(({ mode }) => {
  const target = loadEnv(mode, process.cwd(), '').REHOME_BACKEND || 'http://127.0.0.1:8000';
  const backend = { host: true, proxy: { '/api': target, '/static': target } };
  return { plugins: [tailwindcss(), sveltekit()], server: backend, preview: backend };
});
