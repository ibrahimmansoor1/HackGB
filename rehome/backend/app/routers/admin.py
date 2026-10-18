"""Demo helpers. Seed runs without the model (items are pre-parsed)."""
from fastapi import APIRouter
from app.agents import orchestrator
from app.core import db
from app.schemas import ParsedItem

router = APIRouter(prefix="/api/admin", tags=["admin"])

SEED = [
    ("outerwear", "puffer jacket", "black", "M", "like new", "winter", ["insulated", "hooded", "water-resistant"]),
    ("outerwear", "wool peacoat", "navy", "L", "good", "winter", ["wool", "warm", "lined"]),
    ("outerwear", "rain shell", "yellow", "S", "good", "all", ["waterproof", "lightweight", "hooded"]),
    ("footwear", "snow boots", "brown", "9", "good", "winter", ["insulated", "waterproof", "high-top"]),
    ("footwear", "running shoes", "gray", "10", "like new", "all", ["breathable", "cushioned"]),
    ("accessories", "knit beanie", "red", None, "new", "winter", ["wool", "warm"]),
    ("accessories", "insulated gloves", "black", "M", "good", "winter", ["insulated", "waterproof"]),
    ("tops", "fleece pullover", "green", "M", "good", "winter", ["fleece", "warm", "breathable"]),
    ("tops", "linen shirt", "white", "L", "like new", "summer", ["lightweight", "breathable"]),
    ("bottoms", "snow pants", "black", "M", "fair", "winter", ["insulated", "waterproof"]),
    ("kids", "kids winter coat", "pink", "6T", "good", "winter", ["insulated", "hooded"]),
    ("home", "wool blanket", "beige", None, "good", "winter", ["wool", "warm"]),
    ("home", "desk lamp", "white", None, "good", None, ["led", "adjustable"]),
    ("electronics", "space heater", "black", None, "like new", "winter", ["portable", "thermostat"]),
    ("home", "box fan", "white", None, "good", "summer", ["portable", "quiet"]),
]


@router.post("/seed")
async def seed():
    for cat, item, color, size, cond, season, attrs in SEED:
        parsed = ParsedItem(category=cat, item=item, color=color, size=size, condition=cond,
                            season=season, attributes=attrs,
                            summary=f"{color.capitalize()} {item}"
                                    + (f", size {size}" if size else "") + f", {cond}.")
        await orchestrator.store(parsed, None, "02115", "demo_donor", None, db.new_item_id())
    return {"seeded": len(SEED)}
