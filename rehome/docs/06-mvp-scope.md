# 06 · MVP scope and plan

**Deadline:** Devpost submission by **12:00 PM CDT, Sunday Oct 18, 2026**. Judging expo 1:30 PM.
**Judging weights:** Technical implementation 25% · Impact 25% · Innovation 20% · UX/design 15% · Presentation 15%.

## Must work for the demo (MVP)

- [ ] Donor uploads a photo → parsed item (Gemini) → Donate → item is searchable
- [ ] Requester types a need → ranked matches with reasons (pgvector on Tiger) → claim one → reserved
- [ ] Activity feed shows agent steps live
- [x] Seeded inventory of 18 varied items with photos (`POST /api/admin/seed`)
- [ ] Sell → price range + comps + listing draft
- [ ] Impact dashboard reads `/api/impact` (continuous aggregate)
- [ ] Deployed: backend on Vultr or DigitalOcean, frontend on a GoDaddy domain

## Build order

| # | Step | Demo-critical |
|---|---|---|
| 1 | Tiger tables (`items`, `events`, plus `requests`, `matches`) and `core/db.py` on Postgres | ✅ |
| 2 | Input parser on Gemini | ✅ |
| 3 | Donation step with Modal embeddings | ✅ |
| 4 | Requester agent + vector search + ranking + accept | ✅ |
| 5 | Pricing agent + eBay Browse API | |
| 6 | Continuous aggregate + `/api/impact` + dashboard | |
| 7 | Deploy backend (Vultr or DigitalOcean), frontend on GoDaddy domain | |
| 8 | Kiosk, only if time remains | |

Steps 1–4 are the demo-critical loop. Frontend builds against stub mode in parallel. **Freeze `main` before the deadline** and record the demo video; stretch work only on branches after that.

## Stretch (only after MVP is solid)

1. Post a sell draft to Nostr/Shopstr (`POST /api/items/{draft_id}/list`, built); 30-day rule with "simulate 30 days" button (built — ibrahim)
2. Hardware kiosk: webcam capture + distance-sensor prompts
3. Voice input on requester page
4. Real handoff method (pickup / drop-off point / shipping); currently undecided

## Owners

| Area | Owner | Files |
|---|---|---|
| Agent prompts, orchestrator | _TBD_ | `backend/app/agents/` |
| Tiger DB + embeddings | _TBD_ | `backend/app/core/db.py`, `core/llm.py` |
| Pricing + eBay | _TBD_ (confirm Browse API access first) | `agents/pricing.py`, `integrations/ebay.py` |
| API routes | _TBD_ | `backend/app/routers/` |
| Frontend + dashboard | _TBD_ | `frontend/` |
| Deploy + domain | _TBD_ | – |
| Marketplace (Nostr/Shopstr) + 30-day | ibrahim | `backend/app/integrations/marketplace.py` |
| Kiosk (stretch) | _TBD_ | `kiosk/` (create) |
| Pitch, slides, Devpost video | _TBD_ | `docs/07-demo-script.md` |

## Working together

Repo: `github.com/shuja-waraich-03/HackGB`. Team of 4. Work on branches, merge via PR into `dev`; `dev` → `main` when it runs. Never commit `.env`.

## Definition of done for any feature

Works from the frontend, emits events, matches the docs, merged, and the target branch still runs (tests pass).
