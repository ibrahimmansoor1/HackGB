"""Requester agent: free text + zip -> StructuredQuery (R2 -> R3).
Pure function: never touches the DB. Prompt spec in docs/05-agents.md."""
from pydantic import ValidationError
from app.agents import stub_rules
from app.core import config, llm
from app.schemas import StructuredQuery

SYSTEM_PROMPT = f"""You turn a person's request for a donated item into a search query.
Infer practical context the person did not say: climate from the location
and month, activity, age group. Translate that context into concrete item
attributes from this vocabulary: {", ".join(stub_rules.ATTRIBUTE_VOCAB)}.
Return ONLY a JSON object with exactly these keys: needs, inferred_context,
must_have, nice_to_have, size, search_text.
- needs: the core items, as short noun phrases.
- must_have: attributes without which the item would not serve the need.
- search_text: one line combining needs and attributes; no location names.
No prose, no markdown fences."""


async def parse_request(text: str, zip_code: str) -> StructuredQuery:
    if config.USE_STUBS:
        return _stub(text, zip_code)
    user = f"Request: {text}\nZip code: {zip_code}"
    for attempt in range(2):
        try:
            raw = await llm.complete_json(SYSTEM_PROMPT, user)
            return StructuredQuery.model_validate(raw)
        except (ValidationError, ValueError):
            if attempt == 1:
                raise


def _stub(text: str, zip_code: str = "") -> StructuredQuery:
    """Keyword rules: place/month/zip -> climate -> catalog attributes.
    See agents/stub_rules.py."""
    return StructuredQuery.model_validate(stub_rules.parse_need(text, zip_code))
