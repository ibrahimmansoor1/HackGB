# 03 · Data model

Works as SQL tables or as document collections. If the sponsor DB is document/vector-based, store `embedding` inline on `items` and `requests`.

`writer` = which component sets the field.

## users *(optional for MVP; hardcode a demo donor and requester)*

| Field | Type | Writer | Notes |
|---|---|---|---|
| id | string PK | app | |
| name | string | app | |
| role | string | app | `donor` or `requester` |
| zip | string | app | |

## items

| Field | Type | Writer | Notes |
|---|---|---|---|
| id | string PK | orchestrator | `itm_xxxx` |
| donor_id | string FK | app | |
| image_url | string \| null | orchestrator | absolute URL: `PUBLIC_BASE_URL` + `/static/uploads/<id>.<ext>` (demo items: `SEED_IMAGE_BASE_URL/<name>.png` if set, else `/static/seed/<name>.png`); `null` if no photo |
| note | string | app | donor's free text |
| zip | string | app | |
| category | string | parser | e.g. `outerwear` |
| item | string | parser | e.g. `puffer jacket` |
| color | string | parser | |
| size | string \| null | parser | |
| condition | string | parser | `new`, `like new`, `good`, `fair` |
| season | string \| null | parser | `winter`, `summer`, `all` |
| attributes | string[] | parser | e.g. `["insulated","hooded"]` |
| summary | string | parser | one sentence |
| embedding | float[] | orchestrator | from `summary + attributes` |
| status | string | orchestrator | `available` · `listed` · `reserved` · `donated` |
| created_at | timestamp | orchestrator | |

## requests

| Field | Type | Writer | Notes |
|---|---|---|---|
| id | string PK | orchestrator | `req_xxxx` |
| requester_id | string FK | app | |
| raw_text | string | app | |
| zip | string | app | |
| need | string | requester agent | |
| inferred_context | string[] | requester agent | |
| must_have | string[] | requester agent | |
| nice_to_have | string[] | requester agent | |
| size | string \| null | requester agent | |
| search_text | string | requester agent | what gets embedded |
| embedding | float[] | orchestrator | |
| status | string | orchestrator | `open` · `matched` · `closed` |
| created_at | timestamp | orchestrator | |

## matches

| Field | Type | Writer | Notes |
|---|---|---|---|
| id | string PK | orchestrator | |
| request_id | string FK | orchestrator | |
| item_id | string FK | orchestrator | |
| score | float | orchestrator | similarity, 0–1 |
| rank | int | orchestrator | 1 = best |
| reason | string | orchestrator | one line shown to requester |
| status | string | orchestrator | `suggested` · `accepted` |

## agent_events

| Field | Type | Writer | Notes |
|---|---|---|---|
| id | int PK | events.py | auto-increment; feed polls `?after=<id>` |
| agent | string | events.py | `orchestrator` · `parser` · `requester` |
| item_id | string \| null | events.py | |
| request_id | string \| null | events.py | |
| message | string | events.py | human-readable, shown on screen |
| created_at | timestamp | events.py | |

## listings *(stretch)*

| Field | Type | Writer | Notes |
|---|---|---|---|
| id | string PK | orchestrator | `lst_xxxx` |
| item_id | string FK | orchestrator | |
| platform | string | orchestrator | `nostr` (NIP-99 classified, shown on Shopstr). Roadmap: `ebay`, `etsy`, `shopify` |
| external_id | string | orchestrator | Nostr event id (hex) |
| price | float | orchestrator | USD, from `suggest_price` |
| listed_at | timestamp | orchestrator | = the event's `published_at` |
| expires_at | timestamp | orchestrator | `listed_at + 30 days` |
| url | string | orchestrator | public link, `https://shopstr.store/listing/<naddr>` |
| status | string | orchestrator | `active` · `expired` |
| dry_run | bool | orchestrator | `true` = signed locally, never sent to relays |
| relays_accepted | string[] | orchestrator | relays that stored the event (`[]` in dry run) |

The Nostr event never contains `donor_id`, `note`, or other personal data: only catalog fields, price, and `location` (`LISTING_LOCATION`, else the item's zip).

## Status lifecycle

```
items:     available ──(stretch)──▶ listed ──30d unsold──▶ available
               │                       │
               └──matched──▶ reserved ─┴─▶ donated
requests:  open ──▶ matched ──▶ closed
listings:  active ──30d (simulate-expiry)──▶ expired
```
