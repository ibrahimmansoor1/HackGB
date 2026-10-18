# 06 · MVP scope and plan

## Must work for the demo (MVP)

- [ ] Donor uploads a photo → parsed item appears in inventory
- [ ] Requester types a need → ranked matches with reasons
- [ ] Activity feed shows agent steps live
- [x] Seeded inventory of 18 varied items with photos (`POST /api/admin/seed`)
- [ ] Runs from a clean clone with the README steps

## Stretch (only after MVP is solid)

1. 30-day rule with a "simulate 30 days" button (easiest)
2. Marketplace listing on Nostr, visible on Shopstr (one successful live post is enough). eBay/Etsy/Shopify are roadmap.
3. Hardware kiosk: webcam capture + distance-sensor prompts
4. Voice input on requester page
5. Swap model provider to Gemini if credits arrive

## Owners

| Area | Owner | Files |
|---|---|---|
| Agent prompts, orchestrator | _TBD_ | `backend/app/agents/` |
| DB + embeddings | _TBD_ | `backend/app/core/db.py`, `core/llm.py` |
| API routes | _TBD_ | `backend/app/routers/` |
| Frontend | _TBD_ | `frontend/` |
| Marketplace (Nostr/Shopstr) + 30-day (stretch) | ibrahim | `backend/app/integrations/marketplace.py` |
| Kiosk (stretch) | _TBD_ | `kiosk/` (create) |
| Pitch, slides, Devpost video | _TBD_ | `docs/07-demo-script.md` |

## Build order

1. **Lock contracts** — everyone agrees on `03`, `04`, `05`. Nothing else starts until this is done.
2. **Parallel work:**
   - Frontend builds against stub responses (backend stubs already return fake data).
   - Backend wires `llm.py` to Modal; test parser and requester agents alone with a script.
   - DB owner swaps the in-memory stub for the sponsor DB with vector search.
3. **Integrate** donor path end to end, then requester path.
4. **Seed data** and tune `MATCH_THRESHOLD` and prompts on real searches.
5. **Activity feed** polish for the demo screen.
6. **Freeze** before the 11 a.m. submission announcement; record the video; then stretch goals on a branch only.

## Definition of done for any feature

Works from the frontend, emits events, matches the docs, merged to `main`, `main` still runs.
