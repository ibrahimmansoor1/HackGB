// The ONLY file that talks to the backend. Contract: docs/04-api-contract.md
import { env } from '$env/dynamic/public';

export const BASE = env.PUBLIC_API_URL || 'http://localhost:8000';

async function handle(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

/** D1: donate an item. Returns the parsed Item. */
export async function donateItem({ image, note, zip }) {
  const form = new FormData();
  if (image) form.append('image', image);
  if (note) form.append('note', note);
  form.append('zip', zip);
  return handle(await fetch(`${BASE}/api/items`, { method: 'POST', body: form }));
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
