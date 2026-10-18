"""Demo inventory for POST /api/admin/seed: 18 pre-parsed items (fields per
docs/03 items). Pure data; the orchestrator stores it. Photos live in
static/seed/<photo>.png (scripts/make_seed_images.py draws them)."""

# (category, item, color, size, condition, season, attributes, note, zip, photo)
SEED_ITEMS = [
    ("outerwear", "puffer jacket", "black", "M", "like new", "winter",
     ["insulated", "hooded", "water-resistant"],
     "Wore it one winter, no rips. Too small for me now.", "54301", "puffer-jacket"),
    ("outerwear", "down parka", "olive", "L", "good", "winter",
     ["insulated", "waterproof", "hooded", "lined"],
     "Heavy parka, kept me warm through two Green Bay winters.", "54302", "down-parka"),
    ("outerwear", "wool peacoat", "navy", "L", "good", "winter", ["wool", "warm", "lined"],
     "Classic peacoat, dry cleaned.", "54304", "wool-peacoat"),
    ("outerwear", "rain shell", "yellow", "S", "good", "all",
     ["waterproof", "lightweight", "hooded"],
     "Packs into its own pocket.", "54311", "rain-shell"),
    ("footwear", "snow boots", "brown", "9", "good", "winter",
     ["insulated", "waterproof", "warm"], "Men's 9, rated to -20F.", "54301", "snow-boots"),
    ("footwear", "running shoes", "gray", "10", "like new", "all",
     ["breathable", "cushioned", "lightweight"],
     "Bought the wrong size, ran in them twice.", "54303", "running-shoes"),
    ("footwear", "work boots", "tan", "11", "fair", "all", ["leather", "steel-toe", "durable"],
     "Scuffed but solid. Steel toe.", "54313", "work-boots"),
    ("accessories", "knit beanie", "red", None, "new", "winter", ["wool", "warm"],
     "Hand-knit, never worn.", "54302", "knit-beanie"),
    ("accessories", "insulated gloves", "black", "M", "good", "winter",
     ["insulated", "waterproof", "warm"], "Ski gloves, one season.", "54301", "insulated-gloves"),
    ("tops", "fleece pullover", "green", "M", "good", "winter", ["fleece", "warm", "breathable"],
     "Quarter-zip fleece.", "54304", "fleece-pullover"),
    ("tops", "linen shirt", "white", "L", "like new", "summer", ["lightweight", "breathable"],
     "Button-down, great for hot days.", "54311", "linen-shirt"),
    ("tops", "dress shirt", "blue", "15.5/33", "like new", "all", ["wrinkle-free", "formal"],
     "Good for a job interview.", "54303", "dress-shirt"),
    ("bottoms", "snow pants", "black", "M", "fair", "winter", ["insulated", "waterproof"],
     "Some wear on the cuffs, still waterproof.", "54302", "snow-pants"),
    ("kids", "kids winter coat", "pink", "6T", "good", "winter",
     ["insulated", "hooded", "water-resistant"], "My daughter outgrew it.", "54301",
     "kids-winter-coat"),
    ("home", "wool blanket", "beige", None, "good", "winter", ["wool", "warm"],
     "Queen size, washed.", "54304", "wool-blanket"),
    ("home", "cookware set", "silver", None, "good", None, ["stainless steel", "dishwasher-safe"],
     "Three pots and two pans, moving and downsizing.", "54313", "cookware-set"),
    ("home", "desk lamp", "white", None, "good", None, ["led", "adjustable"],
     "LED, adjustable arm.", "54311", "desk-lamp"),
    ("electronics", "space heater", "black", None, "like new", "winter",
     ["portable", "thermostat", "warm"], "Tip-over shutoff, used one month.", "54303",
     "space-heater"),
]


def summary(color: str, item: str, size: str | None, condition: str,
            attributes: list[str]) -> str:
    """'Black puffer jacket, size M, like new: insulated, hooded, water-resistant.'"""
    text = f"{color.capitalize()} {item}" + (f", size {size}" if size else "") + f", {condition}"
    return f"{text}: {', '.join(attributes[:3])}."
