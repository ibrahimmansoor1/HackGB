// The ONLY file that talks to the backend. Contract: docs/04-api-contract.md
import { env } from '$env/dynamic/public';

// Trailing slash removed so `${BASE}/api/...` never becomes `//api`.
export const BASE = (env.PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

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

/** Hand a draft to the concierge agent. Returns { action, summary, steps, listing, ... }. */
export async function handleDraft(draftId, preference = 'auto') {
  return handle(
    await fetch(`${BASE}/api/items/${draftId}/handle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preference })
    })
  );
}

/** S1: price a draft. Returns { suggested_price, comps, listing_draft, basis }. */
export async function sellDraft(draftId) {
  return handle(await fetch(`${BASE}/api/items/${draftId}/sell`, { method: 'POST' }));
}

/** S6: list a draft for sale on Shopstr at `price` (category default if omitted),
 *  posting `title`/`description` (the /sell quote's listing_draft; template if omitted).
 *  Returns { item, listing }. */
export async function postDraft(draftId, price, { title, description } = {}) {
  const body = {};
  if (price) body.price = price;
  if (title?.trim()) body.title = title.trim();
  if (description?.trim()) body.description = description.trim();
  const init = { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body) };
  return handle(await fetch(`${BASE}/api/items/${encodeURIComponent(draftId)}/post`, init));
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

/** A1: claim a match. Returns { match_id, item_id, status, donor_notified, handoff }. */
export async function acceptMatch(requestId, itemId) {
  return handle(
    await fetch(`${BASE}/api/matches/accept`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_id: requestId, item_id: itemId })
    })
  );
}

/** Activity feed: events with id > after. */
export async function getEvents(after = 0) {
  return handle(await fetch(`${BASE}/api/events?after=${after}`));
}

/** Impact dashboard: { totals, by_category, hourly }. */
export async function getImpact() {
  return handle(await fetch(`${BASE}/api/impact`));
}

export async function listItems(status = 'available') {
  return handle(await fetch(`${BASE}/api/items?status=${status}`));
}

/** Marketplace: list an available item (itm_…) or a sell draft (drf_…) on Nostr
 *  (shows on Shopstr), at `price` if given. Returns { item, listing }.
 *  Errors: 404 unknown/used draft, 409 item not available, 502 no relay accepted it. */
export async function listItem(itemId, price) {
  const init = { method: 'POST' };
  if (price) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify({ price });
  }
  return handle(await fetch(`${BASE}/api/items/${encodeURIComponent(itemId)}/list`, init));
}

/** Marketplace listings, newest first, each with its item. status: '' | 'active' | 'expired'. */
export async function getListings(status = '') {
  return handle(await fetch(`${BASE}/api/listings${status ? `?status=${status}` : ''}`));
}

/** Demo: treat active listings as 30 days old; unsold items go back to the donation pool. */
export async function simulateExpiry() {
  return handle(await fetch(`${BASE}/api/admin/simulate-expiry`, { method: 'POST' }));
}
