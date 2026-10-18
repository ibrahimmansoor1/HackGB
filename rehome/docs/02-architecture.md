# 02 · Architecture

## Components

| Component | Where | Responsibility |
|---|---|---|
| Donor app | `frontend/src/routes/donate` | Upload photo + note |
| Requester app | `frontend/src/routes/request` | Submit need + zip, show matches |
| Activity feed | `frontend/src/lib/ActivityFeed.svelte`, shown at `/feed` | Poll and display agent events |
| Orchestrator | `backend/app/agents/orchestrator.py` | Routes work to agents, embeds, reads/writes DB, ranks |
| Parser agent | `backend/app/agents/parser.py` | Photo + note → item JSON (vision LLM) |
| Requester agent | `backend/app/agents/requester.py` | Need text → query JSON (text LLM) |
| Inventory DB | `backend/app/core/db.py` | Items, requests, matches, events, vectors |
| LLM client | `backend/app/core/llm.py` | Calls Modal (or Gemini) for completions and embeddings |

## Data flow

```mermaid
flowchart TD
  DA[Donor app] -- "D1 photo + note" --> O[Orchestrator]
  O -- "D2 raw input" --> P[Parser agent]
  P -- "D3 item JSON" --> O
  O -- "D4 item + vector (write)" --> DB[(Inventory DB)]

  RA[Requester app] -- "R1 need + zip" --> O
  O -- "R2 raw text" --> R[Requester agent]
  R -- "R3 query JSON" --> O
  O -- "R4 query vector (search)" --> DB
  DB -- "R5 top-k items" --> O
  O -- "R6 ranked matches" --> RA

  O -. "events" .-> F[Activity feed]
```

### Donor path

1. **D1** `POST /api/items` with image file, note, zip.
2. **D2** Orchestrator sends image + note to parser agent.
3. **D3** Parser returns `ParsedItem` JSON (see `05-agents.md`).
4. **D4** Orchestrator embeds `summary + attributes`, writes an `items` row with `status = available`.

### Requester path

1. **R1** `POST /api/requests` with text and zip.
2. **R2** Orchestrator sends text + zip to requester agent.
3. **R3** Requester returns `StructuredQuery` JSON.
4. **R4** Orchestrator embeds `search_text`, runs vector search filtered to `status = available`.
5. **R5** DB returns top-k candidates with similarity scores.
6. **R6** Orchestrator drops candidates below `MATCH_THRESHOLD`, boosts ones satisfying `must_have`, writes a one-line `reason` per match, stores `matches` rows, marks the top item `reserved`, returns the list.

## Design rules

- Only the orchestrator touches the DB (keeps agents testable as pure prompt → JSON functions).
- Apps only talk to the orchestrator through the HTTP API.
- Every step emits an event to `agent_events`.

## Stretch flow: eBay + 30-day rule

```mermaid
flowchart LR
  I[Item available] --> L[Post to eBay sandbox<br/>status = listed]
  L -->|sold| S[Remove from inventory]
  L -->|30 days, unsold| A[status = available<br/>donation pool]
```

For the demo, a `POST /api/admin/simulate-expiry` endpoint fast-forwards the 30 days.
