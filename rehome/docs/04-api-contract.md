# 04 · API contract

Base URL: `http://localhost:8000` locally; the deployed backend (Vultr or DigitalOcean) in production. All responses are JSON. Errors use FastAPI's default `{"detail": "..."}` with a 4xx/5xx code.

This file is the contract between frontend and backend. Change it here first.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness + stub flags |
| POST | `/api/items/parse` | Parse photo/text into a draft; offer sell or donate |
| POST | `/api/items/{draft_id}/sell` | Price range, comps, listing draft |
| POST | `/api/items/{draft_id}/donate` | Embed + insert; item becomes searchable; matchmaker offers it to open requests |
| POST | `/api/items/{draft_id}/handle` | Concierge agent prices it, checks demand, then lists or donates it |
| POST | `/api/items/{draft_id}/post` | List a draft on Shopstr at a price |
| GET | `/api/items?status=` | List inventory |
| POST | `/api/requests` | Need → ranked matches (nothing reserved) |
| POST | `/api/matches/accept` | Claim a match; reserves the item |
| GET | `/api/events?after=<id>` | Activity feed polling |
| GET | `/api/impact` | Stats from the continuous aggregate |
| POST | `/api/admin/seed` | Demo inventory |

---

## `GET /api/health`

```json
{ "status": "ok", "stubs": true, "db": "memory", "marketplace": "dry_run" }
```
`db` is `"tiger"` when `DATABASE_URL` is set, else `"memory"`. `marketplace` is `"live"` when listings really go to Nostr relays (`NOSTR_NSEC` set and `MARKETPLACE_DRY_RUN=false`), else `"dry_run"`.

---

## `POST /api/items/parse` — parse a donation (D1 → D4)

**Request:** `multipart/form-data`

| Field | Type | Required |
|---|---|---|
| images | file(s), jpg/png/webp, ≤ 10 MB each | one of images or text |
| text | string | one of images or text |
| zip | string | yes |
| donor_id | string | no (defaults to `demo_donor`) |

**Response `201`:**
```json
{
  "draft_id": "drf_0007",
  "item": {
    "category": "outerwear",
    "item": "puffer jacket",
    "brand": "Columbia",
    "color": "black",
    "size": "M",
    "condition": "like new",
    "season": "winter",
    "attributes": ["insulated", "hooded", "water-resistant"],
    "summary": "Black hooded Columbia puffer jacket, size M, like new."
  },
  "image_url": "http://localhost:8000/static/uploads/drf_0007.jpg",
  "options": ["sell", "donate"]
}
```
Nothing is written to `items` yet. `image_url` is the first photo (`null` without one). Drafts expire 24 h after parsing.

**Errors:** `400` neither images nor text (blank text and empty files count as none) · `413` image over 10 MB · `415` image is not JPG, PNG, or WebP · `422` missing `zip` · `502` parser model failed.

---

## `POST /api/items/{draft_id}/sell` — price it

No request body.

**Response `200`:**
```json
{
  "draft_id": "drf_0007",
  "suggested_price": { "low": 35, "high": 55, "currency": "USD" },
  "comps": [
    { "title": "Columbia Men's Puffer Jacket M Black", "price": 49.99,
      "condition": "Pre-owned", "source": "ebay", "url": "https://www.ebay.com/itm/..." }
  ],
  "listing_draft": {
    "title": "Columbia Black Hooded Puffer Jacket, Men's M, Like New",
    "description": "Warm insulated puffer with hood..."
  },
  "basis": "active listings"
}
```
`basis` is `"active listings"` when comps came from the eBay Browse API (UI labels prices "currently listed for"), or `"estimate"` when eBay was unavailable and the category × condition heuristic was used (`comps: []`).

**Errors:** `404` unknown or expired draft · `502` pricing model failed.

---

## `POST /api/items/{draft_id}/donate` — donate it

**Request:** `application/json`
```json
{ "pickup_zip": "54311" }
```
The body is optional, and so is `pickup_zip`; it defaults to the draft's `zip`.

**Response `201`:**
```json
{ "item_id": "itm_0142", "status": "available",
  "message": "Thanks! Your puffer jacket is now searchable. 1 open request nearby could use it.",
  "waiting_requests": ["req_0031"] }
```
The draft is consumed. The **matchmaker agent** then checks open (not `closed`) requests against the new item; each that fits gets it as a `suggested` match (claimable with `/api/matches/accept`), moves from `open` to `matched`, and is listed in `waiting_requests`.

---

## `POST /api/items/{draft_id}/handle` — let the agents handle it

Hands the draft to the **concierge agent** (docs/05): it prices the item, checks local demand, then lists or donates it.

**Request** (optional): `{ "preference": "auto" }`: `auto` (the agent decides), `sell`, or `donate`.

**Response `200`:**
```json
{
  "run_id": "run_3f9c2a1b7e",
  "draft_id": "drf_0007",
  "action": "donated",
  "item_id": "itm_0142",
  "summary": "I donated your puffer jacket because 1 person nearby is already looking for one and offered it to them.",
  "brain": "modal",
  "steps": ["get_price_quote", "check_local_demand", "donate_item"],
  "price_quote": { "low": 15, "high": 23, "currency": "USD" },
  "waiting_requests": ["req_0031"],
  "listing": null
}
```
`action` is `listed` (then `listing` is the Shopstr listing) or `donated`. `brain` is `modal` when the Modal model made every decision, `rules` when the offline rule policy did (no Modal, or the model failed and rules finished the job). The draft is consumed.

**Errors:** `404` unknown, expired, or already-used draft · `422` bad `preference` · `502` the run couldn't list or donate (e.g. no relay accepted the listing).

---

## `POST /api/items/{draft_id}/post` — list a draft for sale

**Request** (optional): `{ "price": 45 }`. Without a price, the category × condition heuristic is used.

**Response `201`:** same as `POST /api/items/{id}/list` (`{item, listing}`). The draft becomes an item and is listed (`listed`); unsold after 30 days, the expiry rule puts it in the donation pool. Doesn't count as `item_donated`.

**Errors:** `404` unknown, expired, or already-used draft · `422` price ≤ 0 · `502` no relay accepted it (the item stays `available`, i.e. in the donation pool).

**Errors:** `404` unknown, expired, or already-used draft.

---

## `POST /api/items` — one-step donate *(legacy shortcut)*

Same multipart fields as `/parse` (single `image` + `note`), parses and donates in one call, returns the full `Item`. Same errors as `/parse`. Kept so existing tests and the scaffold frontend keep working; **remove once the frontend uses `/parse` + `/donate`.**

---

## `GET /api/items?status=available` — list inventory

**Response `200`:** `{ "items": [ Item, ... ] }`. `Item` = `ParsedItem` fields + `id`, `donor_id`, `note`, `zip`, `image_url`, `status`, `created_at` (`embedding` is never returned). `status` is optional; any value other than `available`, `listed`, `reserved`, `donated` is a `422`.

---

## `POST /api/requests` — request an item (R1 → R6)

**Request:** `application/json`
```json
{
  "text": "snow clothes, moving to Chicago in December",
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
    "needs": ["winter coat", "snow pants", "boots"],
    "inferred_context": ["sub-freezing winters", "snow"],
    "must_have": ["insulated", "water-resistant"],
    "nice_to_have": ["hooded"],
    "size": null,
    "search_text": "insulated water-resistant winter coat snow pants boots"
  },
  "matches": [
    {
      "item_id": "itm_0142",
      "title": "puffer jacket",
      "rank": 1,
      "score": 0.89,
      "reason": "Insulated and water-resistant, built for Chicago winters",
      "item": { "...": "Item object" }
    }
  ]
}
```
If nothing clears the threshold: `"status": "open"`, `"matches": []`.

`score` is raw similarity (0–1); `rank` is the order after re-ranking (docs/05), so rank 1 can have a lower `score` than rank 2. `title` = the item's `item` field (brand prefixed when known). **Nothing is reserved here**; the requester claims with `/api/matches/accept`.

---

## `POST /api/matches/accept` — claim a match

**Request:**
```json
{ "request_id": "req_0031", "item_id": "itm_0142" }
```

**Response `200`:**
```json
{
  "match_id": "mat_0088",
  "item_id": "itm_0142",
  "status": "reserved",
  "donor_notified": true,
  "handoff": { "method": "pickup", "zip": "54311", "message": "Reserved. The donor has been notified; pickup in 54311." }
}
```
Exchange method is undecided; for now `handoff.method` is always `"pickup"` and notification is an event only. The request becomes `closed`.

**Errors:** `404` unknown request, or the item wasn't one of its matches · `409` item no longer `available` (reserved by someone else, listed, or being listed), or the request is already `closed`.

---

## `GET /api/events?after=<id>` — activity feed

Poll every ~1 s. Returns events with `id > after`, oldest first, max 50. Add `run_id=<run_…>` to get only one agent run's steps (the `run_id` comes back from `/handle`). Agent-run events also carry `run_id`, `tool`, `duration_ms`, and `data` (see docs/03); they're `null` elsewhere.

**Response `200`:**
```json
{
  "events": [
    { "id": 17, "agent": "parser", "event_type": "item_parsed", "category": "outerwear",
      "message": "Identified black Columbia puffer jacket, size M",
      "item_id": null, "request_id": null, "created_at": "2026-10-18T14:02:01Z" }
  ]
}
```

---

## `GET /api/impact` — dashboard stats

Reads `impact_hourly` (continuous aggregate).

**Response `200`:**
```json
{
  "totals": { "items_parsed": 42, "items_donated": 31, "prices_quoted": 9,
              "requests_made": 27, "matches_made": 24, "matches_accepted": 15 },
  "by_category": [ { "category": "outerwear", "items_donated": 12, "matches_accepted": 7 } ],
  "hourly": [ { "bucket": "2026-10-18T13:00:00Z", "event_type": "item_donated", "n": 6 } ]
}
```
`totals` keys are the `event_type` values, pluralized; all six are always present (all time). `by_category` is sorted by `items_donated`, most first. `hourly` covers the last 24 h, summed over categories, oldest first. Without `DATABASE_URL` the same numbers come from the in-memory events.

---

## `POST /api/admin/seed`

Loads the 18-item demo inventory. Returns `{"seeded": 18}`, or `{"seeded": 0}` if already loaded (no duplicates).

---

## Stretch: marketplace (Nostr / Shopstr)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/items/{id}/list` | Price an `items` row, post it as a Nostr classified listing (shows on Shopstr), set `listed` |
| `POST` | `/api/admin/simulate-expiry` | Treat all active listings as 30 days old; close them on Nostr; item → `available` (donation pool) |
| `GET` | `/api/listings?status=active` | List marketplace listings (`status` optional: `active` or `expired`; anything else is `422`) |
| `POST` | `/api/admin/reset` | Start a rehearsal over without restarting: closes active listings (like simulate-expiry), then clears items, requests, matches, and listings; ids restart at `0001`. Events are kept. Returns `{"reset": true, "closed_listings": ["itm_0001", ...]}`; `409` while an item is being listed |

Marketplace posts are **dry runs by default** (signed with a throwaway key, not sent to relays). They go live only when `NOSTR_NSEC` is set and `MARKETPLACE_DRY_RUN=false`. See the README's "Marketplace" section.

**Sell path:** drafts are listed with `POST /api/items/{draft_id}/post` (above). `/list` below lists an existing available item.

### `POST /api/items/{id}/list`

`{id}` is an available item (`itm_…`). Optional body: `{ "price": 45 }` (USD, > 0); without it, the category × condition default is used.

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
- `external_id` is the Nostr event id (hex). `url` opens the listing on Shopstr (an `naddr` link, so it survives republishing). In a dry run the URL is well-formed but nothing was published; `dry_run` is `true` and `relays_accepted` is `[]`.
- `price` comes from a per-category default × condition multiplier (whole dollars, min $1).

**Errors:** `404` item not found · `409` item is not `available` (already listed, reserved, donated, or being listed) · `502` live mode and no relay accepted the event (or `NOSTR_NSEC` is invalid); the item stays `available`. The `detail` names each relay's reason (e.g. `relay.damus.io: relay not connected; nos.lol: timeout`): timeouts on every relay mean the network blocks Nostr (use a hotspot or dry run).

### `POST /api/admin/simulate-expiry`

No request body. Every `active` listing becomes `expired`; each item still `listed` is republished on Nostr with `status=sold` and set back to `available`.

**Response `200`:** `{ "expired": ["itm_0142", "itm_0143"] }` (`[]` when nothing was listed).

### `GET /api/listings`

**Response `200`:** `{ "listings": [ Listing, ... ] }`, newest first. Each is the `listing` shape above **plus `item`** (the full Item object), so a frontend can render a card (photo, title, price) from one call.

### Preview pages (HTML, not JSON)

`GET /listings` (every listing as cards) and `GET /listings/{item_id}` (one item's latest listing: photo, price, status badge, links to Shopstr and njump). Served by the backend for the demo screen, so it doesn't depend on Shopstr's site. `404` if the item was never listed.
