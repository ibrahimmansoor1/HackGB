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
  "image_url": "/static/uploads/itm_0142.jpg",
  "status": "available",
  "created_at": "2026-10-18T14:02:00Z"
}
```
(`embedding` is never returned to the frontend.)

---

## `GET /api/items?status=available` — list inventory

**Response `200`:** `{ "items": [ Item, ... ] }` (same shape as above)

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
| `POST` | `/api/items/{id}/list` | Post item to eBay sandbox, set `listed` |
| `POST` | `/api/admin/simulate-expiry` | Treat all listings as 30 days old; unsold → `available` |
| `POST` | `/api/admin/seed` | Load demo inventory (15–20 items) |
