# 05 · Agents

All agents use one Modal-hosted, vision-capable model with different system prompts. Every agent must return **only JSON** matching its schema; the backend validates with Pydantic and retries once on a validation failure.

Pydantic versions of these schemas live in `backend/app/schemas.py`.

---

## Parser agent

**Input:** image (base64) and/or donor note.
**Output:** `ParsedItem`

```json
{
  "category": "outerwear | tops | bottoms | footwear | accessories | home | electronics | kids | other",
  "item": "string, short noun phrase",
  "color": "string",
  "size": "string or null",
  "condition": "new | like new | good | fair",
  "season": "winter | summer | all | null",
  "attributes": ["string", "..."],
  "summary": "one sentence a buyer would read"
}
```

**System prompt (starting point):**
```
You catalog donated items. Look at the photo and read the donor's note.
Return ONLY a JSON object with exactly these keys: category, item, color,
size, condition, season, attributes, summary.
- category must be one of: outerwear, tops, bottoms, footwear, accessories,
  home, electronics, kids, other.
- attributes: 2–6 short functional properties a person searching might care
  about (e.g. insulated, waterproof, hooded, wool, padded, cordless).
- If the note states a size, use it; otherwise use null. Never guess sizes.
- condition: judge from the photo; prefer the donor's note if it says.
No prose, no markdown fences.
```

---

## Requester agent

**Input:** free text + zip.
**Output:** `StructuredQuery`

```json
{
  "need": "string, the core item",
  "inferred_context": ["string", "..."],
  "must_have": ["attribute", "..."],
  "nice_to_have": ["attribute", "..."],
  "size": "string or null",
  "search_text": "string optimized for similarity search"
}
```

**System prompt (starting point):**
```
You turn a person's request for a donated item into a search query.
Infer practical context the person did not say: climate from the location
and month, activity, age group. Translate that context into concrete item
attributes, using the same vocabulary as a catalog (insulated, waterproof,
hooded, padded, breathable...).
Return ONLY a JSON object with exactly these keys: need, inferred_context,
must_have, nice_to_have, size, search_text.
- must_have: attributes without which the item would not serve the need.
- search_text: one line combining need and attributes; no location names.
No prose, no markdown fences.
```

---

## Orchestrator

Not an LLM loop for the MVP — deterministic Python that calls the agents and the DB. That keeps it fast and predictable for the demo. The LLM is used for one thing inside it: writing match reasons.

**Donor flow:** `parse → embed(summary + attributes) → insert item → emit events`

**Requester flow:**
1. `parse_request → embed(search_text) → vector search (status = available, top_k)`
2. Drop candidates with `score < MATCH_THRESHOLD`.
3. Re-rank: `final = score + 0.05 × (# must_have attributes present)`.
4. One LLM call writes a reason (≤ 12 words) per remaining candidate.
5. Insert `matches`, mark rank-1 item `reserved`, set request `matched`.

**Reason prompt:**
```
For each candidate item, write one reason (max 12 words) explaining why it
fits this request, or what it lacks. Return ONLY a JSON array of
{"item_id": "...", "reason": "..."}.
Request: {query JSON}
Candidates: {list of item summaries + attributes}
```

---

## Events to emit (activity feed)

| Step | agent | Example message |
|---|---|---|
| Upload received | orchestrator | New donation received |
| Parsed | parser | Identified black puffer jacket, size M |
| Stored | orchestrator | Saved itm_0142 as available |
| Request received | orchestrator | New request from 60601 |
| Query built | requester | Inferred snow and sub-freezing winters; needs insulated, water-resistant |
| Search done | orchestrator | Found 3 candidates |
| Matched | orchestrator | Matched itm_0142 (0.89) and reserved it |
| Priced *(stretch)* | orchestrator | Priced itm_0142 at $25 (outerwear, like new) |
| Listed *(stretch)* | orchestrator | Listed itm_0142 on Shopstr — 3/3 relays · or · Listed itm_0142 on Shopstr (dry run) |
| Listing failed *(stretch)* | orchestrator | Couldn't list itm_0142 on Shopstr — 0/3 relays accepted; item stays available |
| Expired *(stretch)* | orchestrator | 30 days unsold — itm_0142 moved to donation pool |
