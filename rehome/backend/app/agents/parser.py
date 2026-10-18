"""Parser agent: photo and/or note -> ParsedItem (D2 -> D3).
Pure function: never touches the DB. Prompt spec in docs/05-agents.md."""
from pydantic import ValidationError
from app.core import config, llm
from app.schemas import ParsedItem

SYSTEM_PROMPT = """You catalog donated items. Look at the photo and read the donor's note.
Return ONLY a JSON object with exactly these keys: category, item, color,
size, condition, season, attributes, summary.
- category must be one of: outerwear, tops, bottoms, footwear, accessories,
  home, electronics, kids, other.
- attributes: 2-6 short functional properties a person searching might care
  about (e.g. insulated, waterproof, hooded, wool, padded, cordless).
- If the note states a size, use it; otherwise use null. Never guess sizes.
- condition: judge from the photo; prefer the donor's note if it says.
No prose, no markdown fences."""


async def parse_item(note: str | None, image_bytes: bytes | None,
                     image_mime: str = "image/jpeg") -> ParsedItem:
    if config.USE_STUBS:
        return _stub(note)
    user = f"Donor note: {note or '(none)'}"
    for attempt in range(2):  # one retry on bad JSON
        try:
            raw = await llm.complete_json(SYSTEM_PROMPT, user, image_bytes, image_mime)
            return ParsedItem.model_validate(raw)
        except (ValidationError, ValueError):
            if attempt == 1:
                raise


def _stub(note: str | None) -> ParsedItem:
    return ParsedItem(
        category="outerwear", item="puffer jacket", color="black", size="M",
        condition="like new", season="winter",
        attributes=["insulated", "hooded", "water-resistant"],
        summary=f"Black hooded puffer jacket, size M. {note or ''}".strip(),
    )
