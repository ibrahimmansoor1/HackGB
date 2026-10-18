// Remember the zip code between pages so people type it once.
const KEY = 'rehome:zip';

export function loadZip() {
  try { return localStorage.getItem(KEY) ?? ''; } catch { return ''; }
}

export function saveZip(zip) {
  try { localStorage.setItem(KEY, zip); } catch { /* private mode: just don't remember */ }
}
