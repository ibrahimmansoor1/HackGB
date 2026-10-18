"""Orchestrator: the ONLY module that reads/writes the database.
Flows and ranking rules are specified in docs/02 and docs/05."""
from app.agents import parser, requester
from app.agents.events import emit
from app.core import config, db, llm
from app.schemas import Item, Match, ParsedItem, RequestOut

REASON_PROMPT = """For each candidate item, write one reason (max 12 words) explaining why it
fits this request, or what it lacks. Return ONLY a JSON array of
{"item_id": "...", "reason": "..."}."""

# Stub embeddings score much lower than real ones.
THRESHOLD = 0.15 if config.USE_STUBS else config.MATCH_THRESHOLD


def _public(row: dict) -> Item:
    return Item.model_validate({k: v for k, v in row.items() if k != "embedding"})


# ---- donor path: D1 -> D4 --------------------------------------------------
async def donate(note: str | None, zip_code: str, donor_id: str,
                 image_bytes: bytes | None, image_mime: str,
                 image_url: str | None, item_id: str) -> Item:
    emit("orchestrator", "New donation received", item_id=item_id)
    parsed = await parser.parse_item(note, image_bytes, image_mime)
    emit("parser", f"Identified {parsed.color} {parsed.item}"
         + (f", size {parsed.size}" if parsed.size else ""), item_id=item_id)
    return await store(parsed, note, zip_code, donor_id, image_url, item_id)


async def store(parsed: ParsedItem, note: str | None, zip_code: str,
                donor_id: str, image_url: str | None, item_id: str) -> Item:
    vec = await llm.embed(f"{parsed.summary} {' '.join(parsed.attributes)} {parsed.item}")
    row = {**parsed.model_dump(), "id": item_id, "donor_id": donor_id, "note": note,
           "zip": zip_code, "image_url": image_url, "status": "available",
           "embedding": vec, "created_at": db.now()}
    db.insert_item(row)
    emit("orchestrator", f"Saved {item_id} as available", item_id=item_id)
    return _public(row)


# ---- requester path: R1 -> R6 ----------------------------------------------
async def handle_request(text: str, zip_code: str, requester_id: str) -> RequestOut:
    req_id = db.new_request_id()
    emit("orchestrator", f"New request from {zip_code}", request_id=req_id)

    query = await requester.parse_request(text, zip_code)
    ctx = ", ".join(query.inferred_context) or "no extra context"
    need = ", ".join(query.must_have) or "nothing specific"
    emit("requester", f"Inferred {ctx}; needs {need}", request_id=req_id)

    qvec = await llm.embed(query.search_text)
    candidates = db.vector_search(qvec, top_k=config.TOP_K)
    emit("orchestrator", f"Found {len(candidates)} candidates", request_id=req_id)

    # threshold + must_have boost
    ranked = []
    for row, score in candidates:
        if score < THRESHOLD:
            continue
        hits = sum(a in row["attributes"] for a in query.must_have)
        ranked.append((row, score, score + 0.05 * hits))
    ranked.sort(key=lambda x: x[2], reverse=True)

    reasons = await _reasons(query, [r for r, _, _ in ranked])
    matches = [Match(item_id=row["id"], rank=i + 1, score=round(score, 3),
                     reason=reasons.get(row["id"], "Similar to what you asked for"),
                     item=_public(row))
               for i, (row, score, _) in enumerate(ranked)]

    status = "matched" if matches else "open"
    db.insert_request({**query.model_dump(), "id": req_id, "requester_id": requester_id,
                       "raw_text": text, "zip": zip_code, "embedding": qvec,
                       "status": status, "created_at": db.now()})
    db.insert_matches([{"request_id": req_id, "item_id": m.item_id, "score": m.score,
                        "rank": m.rank, "reason": m.reason, "status": "suggested"}
                       for m in matches])
    if matches:
        db.update_item_status(matches[0].item_id, "reserved")
        emit("orchestrator", f"Matched {matches[0].item_id} ({matches[0].score}) and reserved it",
             request_id=req_id, item_id=matches[0].item_id)
    else:
        emit("orchestrator", "No good match yet; request left open", request_id=req_id)

    return RequestOut(request_id=req_id, status=status, query=query, matches=matches)


async def _reasons(query, rows: list[dict]) -> dict[str, str]:
    if not rows:
        return {}
    if config.USE_STUBS:
        return {r["id"]: f"{r['item'].capitalize()}: {', '.join(r['attributes'][:3])}" for r in rows}
    cands = [{"item_id": r["id"], "summary": r["summary"], "attributes": r["attributes"]}
             for r in rows]
    try:
        out = await llm.complete_json(REASON_PROMPT,
                                      f"Request: {query.model_dump_json()}\nCandidates: {cands}")
        return {o["item_id"]: o["reason"] for o in out}
    except Exception:
        return {}
