// Fonts are bundled so the kiosk works on bad venue wifi.
import './app.css';
import '@fontsource-variable/bricolage-grotesque/opsz.css';
import '@fontsource-variable/figtree';
import '@fontsource/dm-mono/400.css';
import '@fontsource/dm-mono/500.css';
import { mount } from 'svelte';
import App from './App.svelte';

mount(App, { target: document.getElementById('app') });
