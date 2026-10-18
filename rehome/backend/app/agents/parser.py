"""Parser agent: photo(s) and/or donor text -> ParsedItem (D2 -> D3), on Gemini.
Pure function: never touches the DB. Prompt spec in docs/05-agents.md."""
from pydantic import ValidationError
from app.agents import stub_rules
from app.core import config, llm
from app.schemas import ParsedItem

SYSTEM_PROMPT = f"""You catalog secondhand items. Look at the photo(s) and read the donor's text.
Return ONLY a JSON object with exactly these keys: category, item, brand,
color, size, condition, season, attributes, summary.
- category must be one of: outerwear, tops, bottoms, footwear, accessories,
  home, electronics, kids, other.
- brand and size: read them from a visible tag or the donor's text; otherwise
  null. Never guess.
- attributes: 2-6 short functional properties a person searching might care
  about, chosen from this vocabulary when possible: {", ".join(stub_rules.ATTRIBUTE_VOCAB)}.
- condition: one of new, like new, good, fair. Judge from the photo; prefer
  the donor's text if it says.
- season: winter, summer, all, or null.
- summary: one sentence a buyer would read.
No prose, no markdown fences."""


async def parse_item(text: str | None,
                     images: list[tuple[bytes, str]] | None = None) -> ParsedItem:
    """`images` is a list of (bytes, mime). No GEMINI_API_KEY -> stub parser."""
    images = [(b, m) for b, m in images or [] if b]
    if not config.GEMINI_API_KEY:
        return _stub(text, bool(images))
    user = f"Donor text: {text or '(none)'}"
    for attempt in range(2):  # one retry on bad JSON / schema mismatch
        try:
            raw = await llm.gemini_json(SYSTEM_PROMPT, user, images)
            return ParsedItem.model_validate(raw)
        except (ValidationError, ValueError):
            if attempt == 1:
                raise


def _stub(text: str | None, has_image: bool = False) -> ParsedItem:
    """Deterministic keyword parse of the text; a photo with no text reads as
    the demo jacket. See agents/stub_rules.py."""
    return ParsedItem.model_validate(stub_rules.parse_note(text, has_image))
