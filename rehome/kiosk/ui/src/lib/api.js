// Every ReHome backend call the kiosk makes. server.py forwards /api/* to the backend,
// so these are same-origin. Contract: docs/04-api-contract.md

async function handle(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join('; ') : body.detail;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return body;
}

const postJson = (path, body = {}) =>
  fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

/** Kiosk settings from server.py: { zip, site, backend, fake }. */
export async function config() {
  return handle(await fetch('/config.json'));
}

/** D1: parse the photo into a draft. Returns { draft_id, item, image_url, options }. Nothing is saved yet. */
export async function parse(photo, zip) {
  const form = new FormData();
  form.append('images', photo, 'kiosk.jpg');
  form.append('zip', zip);
  return handle(await fetch('/api/items/parse', { method: 'POST', body: form }));
}

/** Donate the draft: it becomes a searchable item. Returns { item_id, status, message }. */
export async function donate(draftId) {
  return handle(await postJson(`/api/items/${encodeURIComponent(draftId)}/donate`));
}

/** Price the draft from eBay comps. Returns { suggested_price: { low, high }, comps, listing_draft, basis }. */
export async function quote(draftId) {
  return handle(await postJson(`/api/items/${encodeURIComponent(draftId)}/sell`));
}

/** Agent activity: events with id > after. */
export async function events(after = 0) {
  return (await handle(await fetch(`/api/events?after=${after}`))).events;
}

export async function health() {
  return handle(await fetch('/api/health'));
}
