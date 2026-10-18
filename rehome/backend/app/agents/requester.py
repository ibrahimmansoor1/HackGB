"""Requester agent: free text + zip -> StructuredQuery (R2 -> R3).
Pure function: never touches the DB. Prompt spec in docs/05-agents.md."""
from pydantic import ValidationError
from app.core import config, llm
from app.schemas import StructuredQuery

SYSTEM_PROMPT = """You turn a person's request for a donated item into a search query.
Infer practical context the person did not say: climate from the location
and month, activity, age group. Translate that context into concrete item
attributes, using the same vocabulary as a catalog (insulated, waterproof,
hooded, padded, breathable...).
Return ONLY a JSON object with exactly these keys: need, inferred_context,
must_have, nice_to_have, size, search_text.
- must_have: attributes without which the item would not serve the need.
- search_text: one line combining need and attributes; no location names.
No prose, no markdown fences."""


async def parse_request(text: str, zip_code: str) -> StructuredQuery:
    if config.USE_STUBS:
        return _stub(text)
    user = f"Request: {text}\nZip code: {zip_code}"
    for attempt in range(2):
        try:
            raw = await llm.complete_json(SYSTEM_PROMPT, user)
            return StructuredQuery.model_validate(raw)
        except (ValidationError, ValueError):
            if attempt == 1:
                raise


def _stub(text: str) -> StructuredQuery:
    cold = any(w in text.lower() for w in ("chicago", "winter", "cold", "snow", "december"))
    must = ["insulated", "water-resistant"] if cold else []
    return StructuredQuery(
        need=text,
        inferred_context=["sub-freezing winters", "snow"] if cold else [],
        must_have=must, nice_to_have=["hooded"] if cold else [],
        search_text=" ".join([text, *must, "winter" if cold else ""]).strip(),
    )
