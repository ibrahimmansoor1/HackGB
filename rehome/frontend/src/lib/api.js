// The ONLY file that talks to the backend. Contract: docs/04-api-contract.md
import { env } from '$env/dynamic/public';

export const BASE = env.PUBLIC_API_URL || 'http://localhost:8000';

async function handle(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

/** D1: parse photos and/or text into a draft. Returns { draft_id, item, image_url, options }. */
export async function parseItem({ images = [], text, zip }) {
  const form = new FormData();
  for (const image of images) form.append('images', image);
  if (text) form.append('text', text);
  form.append('zip', zip);
  return handle(await fetch(`${BASE}/api/items/parse`, { method: 'POST', body: form }));
}

/** N1: donate a draft. Returns { item_id, status, message }. */
export async function donateDraft(draftId, pickupZip) {
  return handle(
    await fetch(`${BASE}/api/items/${draftId}/donate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(pickupZip ? { pickup_zip: pickupZip } : {})
    })
  );
}

/** R1: request an item. Returns { request_id, status, query, matches }. */
export async function requestItem({ text, zip }) {
  return handle(
    await fetch(`${BASE}/api/requests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, zip })
    })
  );
}

/** Activity feed: events with id > after. */
export async function getEvents(after = 0) {
  return handle(await fetch(`${BASE}/api/events?after=${after}`));
}

export async function listItems(status = 'available') {
  return handle(await fetch(`${BASE}/api/items?status=${status}`));
}
