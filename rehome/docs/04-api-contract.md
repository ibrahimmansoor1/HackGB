# 04 · API contract

Base URL: `http://localhost:8000`. All responses are JSON. Errors use FastAPI's default `{"detail": "..."}` with a 4xx/5xx code.

This file is the contract between frontend and backend. Change it here first.

---

## `GET /api/health`

```json
{ "status": "ok" }
```

---

## `POST /api/items` — donate an item (D1 → D4)

**Request:** `multipart/form-data`

| Field | Type | Required |
|---|---|---|
| image | file (jpg/png/webp, ≤ 10 MB) | one of image or note |
| note | string | one of image or note |
| zip | string | yes |
| donor_id | string | no (defaults to `demo_donor`) |

**Response `201`:**
```json
{
  "id": "itm_0142",
  "category": "outerwear",
  "item": "puffer jacket",
  "color": "black",
  "size": "M",
  "condition": "like new",
  "season": "winter",
  "attributes": ["insulated", "hooded", "water-resistant"],
  "summary": "Black hooded puffer jacket, size M, like new.",
  "image_url": "http://localhost:8000/static/uploads/itm_0142.jpg",
  "status": "available",
  "created_at": "2026-10-18T14:02:00Z"
}
```
(`embedding` is never returned to the frontend.) `image_url` is absolute, built from `PUBLIC_BASE_URL`, so the frontend uses it as is; it is `null` when no photo was sent.

**Errors:** `400` neither image nor note (a blank note counts as none) · `413` image over 10 MB · `415` image is not JPG, PNG, or WebP · `422` missing `zip`.

---

## `GET /api/items?status=available` — list inventory

**Response `200`:** `{ "items": [ Item, ... ] }` (same shape as above). `status` is optional (omit for all items); any value other than `available`, `listed`, `reserved`, `donated` is a `422`.

---

## `POST /api/requests` — request an item (R1 → R6)

**Request:** `application/json`
```json
{
  "text": "need a warm coat, moving to Chicago in December",
  "zip": "60601",
  "requester_id": "demo_requester"
}
```

**Response `201`:**
```json
{
  "request_id": "req_0031",
  "status": "matched",
  "query": {
    "need": "winter coat",
    "inferred_context": ["sub-freezing winters", "snow"],
    "must_have": ["insulated", "water-resistant"],
    "nice_to_have": ["hooded"],
    "size": null,
    "search_text": "insulated water-resistant hooded winter coat"
  },
  "matches": [
    {
      "item_id": "itm_0142",
      "rank": 1,
      "score": 0.89,
      "reason": "Insulated and water-resistant, built for Chicago winters",
      "item": { "...": "Item object" }
    }
  ]
}
```
If nothing clears the threshold: `"status": "open"`, `"matches": []`.

`score` is the raw similarity (0–1); `rank` is the order after re-ranking (docs/05), so rank 1 can have a lower `score` than rank 2. The rank-1 item becomes `reserved`.

---

## `GET /api/events?after=<id>` — activity feed

Poll every ~1 s. Returns events with `id > after`, oldest first, max 50.

**Response `200`:**
```json
{
  "events": [
    { "id": 17, "agent": "parser", "message": "Identified black puffer jacket, size M",
      "item_id": "itm_0142", "request_id": null, "created_at": "2026-10-18T14:02:01Z" }
  ]
}
```

---

## Stretch

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/items/{id}/list` | Price the item, post it as a Nostr classified listing (shows on Shopstr), set `listed` |
| `POST` | `/api/admin/simulate-expiry` | Treat all active listings as 30 days old; close them on Nostr; item → `available` (donation pool) |
| `GET` | `/api/listings?status=active` | List marketplace listings (`status` optional: `active` or `expired`; anything else is `422`) |
| `POST` | `/api/admin/seed` | Load the 18-item demo inventory. Returns `{"seeded": 18}`, or `{"seeded": 0}` if it was already loaded (no duplicates) |

Marketplace posts are **dry runs by default** (signed with a throwaway key, not sent to relays). They go live only when `NOSTR_NSEC` is set and `MARKETPLACE_DRY_RUN=false`. See the README's "Marketplace" section.

### `POST /api/items/{id}/list`

No request body.

**Response `200`:**
```json
{
  "item": { "...": "Item object", "status": "listed" },
  "listing": {
    "id": "lst_0001",
    "item_id": "itm_0142",
    "platform": "nostr",
    "external_id": "78bd148eb093fd3b83d35d8e56f4c790f9e88cbf2dc4b4aff023471d15ee50ff",
    "price": 25.0,
    "listed_at": "2026-10-18T14:05:00Z",
    "expires_at": "2026-11-17T14:05:00Z",
    "url": "https://shopstr.store/listing/naddr1...",
    "nostr_url": "https://njump.me/naddr1...",
    "status": "active",
    "dry_run": false,
    "relays_accepted": ["wss://relay.damus.io", "wss://nos.lol", "wss://relay.primal.net"]
  }
}
```
- `external_id` is the Nostr event id (hex). `url` opens the listing on Shopstr (an `naddr` link, so it survives republishing). In a dry run the URL is well-formed but nothing was published, so it won't resolve; `dry_run` is `true` and `relays_accepted` is `[]`.
- `price` comes from a per-category default × condition multiplier (whole dollars, min $1).

**Errors:** `404` item not found · `409` item is not `available` (already listed, reserved, donated, or being listed) · `502` live mode and no relay accepted the event (or `NOSTR_NSEC` is invalid); the item stays `available`.

### `POST /api/admin/simulate-expiry`

No request body. Every `active` listing becomes `expired`; each item still `listed` is republished on Nostr with `status=sold` (closing the public listing) and set back to `available`.

**Response `200`:**
```json
{ "expired": ["itm_0142", "itm_0143"] }
```
`expired` is `[]` when nothing was listed.

### `GET /api/listings`

**Response `200`:** `{ "listings": [ Listing, ... ] }`, newest first. Each is the `listing` shape above **plus `item`** (the full Item object), so a frontend can render a card (photo, title, price) from one call.

### Preview pages (HTML, not JSON)

`GET /listings` (every listing as cards) and `GET /listings/{item_id}` (one item's latest listing: photo, price, status badge, links to Shopstr and njump). Served by the backend for the demo screen, so it doesn't depend on Shopstr's site. `404` if the item was never listed.
