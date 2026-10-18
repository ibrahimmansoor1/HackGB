"""Deterministic keyword rules used by the agents in stub mode (no model).

Pure functions, no DB, no network. Good enough for the demo to behave
sensibly offline: a note like "black puffer jacket, size M, barely worn"
parses correctly, and "warm coat, moving to Chicago in December" infers cold
weather and asks for insulated, water-resistant outerwear.
"""
import re

# ---- vocabulary ------------------------------------------------------------
# Item nouns -> category. Multi-word nouns are matched before single words.
NOUNS = {
    "outerwear": ["coat", "jacket", "parka", "peacoat", "raincoat", "rain shell", "shell",
                  "windbreaker", "vest", "anorak", "puffer"],
    "tops": ["shirt", "sweater", "hoodie", "pullover", "sweatshirt", "t-shirt", "tee",
             "blouse", "cardigan", "polo", "flannel"],
    "bottoms": ["pants", "jeans", "trousers", "shorts", "skirt", "leggings", "joggers",
                "snow pants", "overalls"],
    "footwear": ["boots", "shoes", "sneakers", "sandals", "cleats", "slippers", "loafers"],
    "accessories": ["hat", "beanie", "gloves", "mittens", "scarf", "backpack", "bag",
                    "umbrella", "belt", "tie"],
    "home": ["blanket", "lamp", "fan", "pan", "pot", "dishes", "plates", "chair", "table",
             "sheets", "pillow", "towels", "comforter", "rug", "curtains", "cookware", "mugs"],
    "electronics": ["laptop", "phone", "heater", "space heater", "charger", "monitor",
                    "keyboard", "headphones", "speaker", "microwave", "tablet", "kettle"],
    "kids": ["stroller", "crib", "car seat", "toy", "toys", "onesie"],
}
KID_WORDS = {"kid", "kids", "child", "children", "toddler", "baby", "youth", "son",
             "daughter", "boys", "girls"}
COLORS = ["black", "white", "gray", "grey", "navy", "blue", "red", "green", "olive",
          "yellow", "orange", "pink", "purple", "brown", "tan", "beige", "cream",
          "silver", "gold", "maroon", "teal", "charcoal"]
# Words that describe the item and belong in its name ("puffer jacket").
MODIFIERS = {"puffer", "wool", "rain", "snow", "winter", "running", "hiking", "leather",
             "denim", "down", "fleece", "knit", "flannel", "desk", "box", "space", "ski",
             "work", "dress", "cast", "iron", "non-stick", "insulated", "thermal", "cotton",
             "linen", "waterproof", "baby", "toddler", "kids", "steel", "toe", "floor"}
# Phrase -> catalog attribute.
ATTRIBUTES = {
    "insulated": ["insulated", "puffer", "down", "padded", "thermal", "quilted"],
    "waterproof": ["waterproof", "gore-tex", "goretex", "rain boots", "rubber"],
    "water-resistant": ["water-resistant", "water resistant", "water-repellent", "dwr"],
    "hooded": ["hooded", "hood", "hoodie"],
    "wool": ["wool", "merino", "cashmere"],
    "fleece": ["fleece", "sherpa"],
    "warm": ["warm", "cozy", "heavy"],
    "lined": ["lined", "lining"],
    "breathable": ["breathable", "mesh", "linen"],
    "lightweight": ["lightweight", "packable", "light weight"],
    "cushioned": ["cushioned", "padded sole"],
    "portable": ["portable"],
    "cordless": ["cordless", "battery"],
    "adjustable": ["adjustable"],
    "led": ["led"],
    "reflective": ["reflective"],
    "non-stick": ["non-stick", "nonstick"],
    "machine-washable": ["machine washable", "machine-washable"],
}
# Shared attribute vocabulary (docs/05): the parser and requester prompts both
# list these so item attributes and must_have line up in vector space.
ATTRIBUTE_VOCAB = list(ATTRIBUTES)
STOP = {"a", "an", "the", "my", "our", "this", "that", "some", "old", "new", "nice", "great",
        "used", "barely", "worn", "gently", "clean", "cute", "big", "small", "little",
        "pair", "of", "and", "or", "warm", "good", "need", "want", "looking", "for"}

# ---- requester context -----------------------------------------------------
COLD_PLACES = ["chicago", "minneapolis", "milwaukee", "green bay", "madison", "wisconsin",
               "minnesota", "michigan", "detroit", "boston", "new york", "denver", "alaska",
               "canada", "buffalo", "toronto", "montreal", "iowa", "north dakota", "maine"]
RAINY_PLACES = ["seattle", "portland", "oregon", "vancouver"]
HOT_PLACES = ["phoenix", "arizona", "miami", "florida", "texas", "houston", "las vegas",
              "los angeles", "san diego", "atlanta"]
COLD_MONTHS = ["november", "december", "january", "february", "march"]
HOT_MONTHS = ["june", "july", "august"]
COLD_WORDS = ["winter", "snow", "cold", "freezing", "blizzard", "ice", "icy"]
HOT_WORDS = ["summer", "heat", "hot", "humid"]
RAIN_WORDS = ["rain", "rainy", "wet", "storm"]
# Zip prefixes with real winters: Chicago, Wisconsin, Minnesota, Michigan, Boston.
COLD_ZIP_PREFIXES = ("600", "601", "602", "603", "604", "605", "606", "607", "608",
                     "53", "54", "55", "56", "48", "49", "021", "022")


# ---- helpers ---------------------------------------------------------------
def _has(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", text) is not None


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z\-]*", text.lower())


def find_noun(text: str) -> tuple[str | None, str | None, int]:
    """Earliest item noun in the text -> (noun, category, position)."""
    low = text.lower()
    best: tuple[str | None, str | None, int] = (None, None, len(low) + 1)
    for cat, nouns in NOUNS.items():
        for noun in sorted(nouns, key=len, reverse=True):
            m = re.search(rf"(?<![a-z]){re.escape(noun)}(?:e?s)?(?![a-z])", low)
            if m and (m.start() < best[2] or
                      (m.start() == best[2] and len(noun) > len(best[0] or ""))):
                best = (noun, cat, m.start())
    return best


def item_phrase(text: str) -> tuple[str | None, str | None]:
    """'black puffer jacket, size M' -> ('puffer jacket', 'outerwear')."""
    noun, cat, pos = find_noun(text)
    if noun is None:
        return None, None
    before = _words(text[:pos])
    mods = []
    for w in reversed(before[-2:]):
        if w in MODIFIERS and w not in STOP:
            mods.insert(0, w)
        else:
            break
    if noun == "puffer":       # "a puffer" on its own means a puffer jacket
        noun = "puffer jacket"
    phrase = " ".join([*mods, noun]) if noun.split()[0] not in mods else noun
    return phrase, cat


def find_size(text: str) -> str | None:
    """Only sizes the person actually stated. Never guesses."""
    m = re.search(r"\bsize\s*:?\s*([a-z0-9.]+(?:/[a-z0-9.]+)?)\b", text, re.I)
    if m:
        size = m.group(1)
        words = {"small": "S", "medium": "M", "large": "L", "xlarge": "XL"}
        return words.get(size.lower(), size.upper() if size.isalpha() else size)
    m = re.search(r"\b(XXS|XS|XXL|XL|XXXL|\d{1,2}T)\b", text)
    return m.group(1) if m else None


def find_color(text: str) -> str | None:
    low = text.lower()
    hits = [(low.find(c), c) for c in COLORS if _has(low, c)]
    if not hits:
        return None
    color = min(hits)[1]
    return "gray" if color == "grey" else color


def find_condition(text: str) -> str:
    low = text.lower()
    if any(_has(low, p) for p in ("like new", "barely", "hardly", "worn once", "mint",
                                  "excellent", "only used once", "used once")):
        return "like new"
    if any(_has(low, p) for p in ("new with tags", "brand new", "never worn", "never used",
                                  "unopened", "nwt", "still in box")):
        return "new"
    if any(_has(low, p) for p in ("fair", "stain", "stained", "scuff", "scuffed", "faded",
                                  "well-loved", "well loved", "some wear", "pilling",
                                  "worn out", "small hole", "missing")):
        return "fair"
    return "good"


def find_attributes(text: str) -> list[str]:
    low = text.lower()
    return [attr for attr, phrases in ATTRIBUTES.items() if any(_has(low, p) for p in phrases)]


# ---- parser stub -------------------------------------------------------------
DEFAULT_PHOTO_ITEM = {   # what the stub "sees" in a photo with no note (demo: a jacket)
    "category": "outerwear", "item": "puffer jacket", "color": "black", "size": None,
    "condition": "like new", "season": "winter",
    "attributes": ["insulated", "hooded", "water-resistant"],
}
CATEGORY_DEFAULT_ATTRS = {
    "outerwear": ["warm"], "footwear": ["durable"], "tops": ["soft"], "bottoms": ["durable"],
    "home": ["household"], "electronics": ["working"], "kids": ["kids"],
    "accessories": ["everyday"], "other": ["reusable"],
}
WINTER_SIGNALS = {"insulated", "wool", "fleece", "warm", "lined"}


def parse_note(note: str | None, has_image: bool) -> dict:
    """Donor note (and whether a photo came with it) -> ParsedItem fields."""
    text = (note or "").strip()
    phrase, cat = item_phrase(text)
    if phrase is None and (has_image or not text):
        base = dict(DEFAULT_PHOTO_ITEM)
        base["color"] = find_color(text) or base["color"]
        base["size"] = find_size(text)
        if text:
            base["condition"] = find_condition(text)
        return _finish(base)

    low = text.lower()
    if any(w in KID_WORDS for w in _words(low)):
        cat = "kids"
        if phrase and not any(phrase.startswith(k) for k in ("kids", "baby", "toddler")):
            phrase = f"kids {phrase}"
    attrs = find_attributes(text)
    if len(attrs) < 2:
        for a in CATEGORY_DEFAULT_ATTRS.get(cat or "other", []):
            if a not in attrs:
                attrs.append(a)
    season = None
    if any(_has(low, w) for w in COLD_WORDS) or WINTER_SIGNALS & set(attrs):
        season = "winter"
    elif any(_has(low, w) for w in ("summer", "linen", "shorts", "sandals")):
        season = "summer"
    elif cat in ("outerwear", "tops", "bottoms", "footwear", "accessories", "kids"):
        season = "all"
    return _finish({"category": cat or "other", "item": phrase or "donated item",
                    "color": find_color(text) or "assorted", "size": find_size(text),
                    "condition": find_condition(text), "season": season,
                    "attributes": attrs[:6]})


def _finish(p: dict) -> dict:
    name = p["item"] if p["color"] == "assorted" else f"{p['color']} {p['item']}"
    summary = name[0].upper() + name[1:]
    if p.get("size"):
        summary += f", size {p['size']}"
    summary += f", {p['condition']}"
    real = [a for a in p["attributes"] if a not in sum(CATEGORY_DEFAULT_ATTRS.values(), [])]
    if real:
        summary += f": {', '.join(real[:3])}"
    p["summary"] = summary + "."
    return p


# ---- requester stub ----------------------------------------------------------
NEEDS_BY_CLIMATE = {
    # climate -> category -> (must_have, nice_to_have)
    "cold": {"outerwear": (["insulated", "water-resistant"], ["hooded"]),
             "footwear": (["insulated", "waterproof"], ["warm"]),
             "accessories": (["warm"], ["wool", "insulated"]),
             "bottoms": (["insulated", "waterproof"], []),
             "tops": (["warm"], ["fleece", "wool"]),
             "kids": (["insulated"], ["hooded", "water-resistant"]),
             None: (["insulated", "water-resistant"], ["hooded"])},
    "rain": {"outerwear": (["waterproof"], ["hooded", "lightweight"]),
             "footwear": (["waterproof"], []),
             None: (["waterproof"], ["hooded"])},
    "hot": {None: (["breathable"], ["lightweight"])},
}
CONTEXT_TEXT = {"cold": ["sub-freezing winters", "snow"], "rain": ["frequent rain"],
                "hot": ["hot weather"]}
CLIMATE_NEED_PREFIX = {"cold": "winter", "rain": "rain", "hot": "summer"}


def climate(text: str, zip_code: str) -> str | None:
    low = text.lower()
    if any(_has(low, m) for m in HOT_MONTHS) or any(_has(low, w) for w in HOT_WORDS):
        return "hot"
    if any(_has(low, m) for m in COLD_MONTHS) or any(_has(low, w) for w in COLD_WORDS):
        return "cold"
    if any(_has(low, w) for w in RAIN_WORDS) or any(_has(low, p) for p in RAINY_PLACES):
        return "rain"
    if any(_has(low, p) for p in COLD_PLACES):
        return "cold"
    if any(_has(low, p) for p in HOT_PLACES):
        return "hot"
    if zip_code and zip_code.strip().startswith(COLD_ZIP_PREFIXES) and \
            item_phrase(text)[1] in ("outerwear", "accessories"):
        return "cold"
    return None


def parse_need(text: str, zip_code: str) -> dict:
    """Free text + zip -> StructuredQuery fields."""
    low = text.lower()
    phrase, cat = item_phrase(text)
    noun_cat = cat
    kid = any(w in KID_WORDS for w in _words(low))
    if kid and cat != "kids":
        cat = "kids" if cat in (None, "outerwear", "tops", "bottoms", "footwear") else cat
    clim = climate(text, zip_code)
    context = list(CONTEXT_TEXT.get(clim, []))
    if kid:
        context.append("for a child")
    must: list[str] = []
    nice: list[str] = []
    if clim:
        table = NEEDS_BY_CLIMATE[clim]
        must, nice = (list(x) for x in table.get(noun_cat, table.get(cat, table[None])))
    if _has(low, "interview") or _has(low, "job"):
        context.append("job interview")
        nice.append("formal")
    for a in find_attributes(text):
        if a not in must and a not in nice and a != "warm":
            nice.append(a)
    if _has(low, "warm") and "warm" not in must and "insulated" not in must:
        must.append("warm")

    noun = phrase or (cat and NOUNS[cat][0]) or text.strip()
    need = noun
    if clim and phrase and not any(phrase.startswith(p) for p in CLIMATE_NEED_PREFIX.values()):
        need = f"{CLIMATE_NEED_PREFIX[clim]} {phrase}"
    # search_text: need + category + attributes; never location names.
    words = [need, cat or "", *must, *nice]
    if clim == "cold":
        words.append("winter")
    search = " ".join(dict.fromkeys(w for w in words if w))
    for place in COLD_PLACES + RAINY_PLACES + HOT_PLACES:
        search = re.sub(rf"\b{re.escape(place)}\b", "", search, flags=re.I)
    return {"needs": [need], "inferred_context": context, "must_have": must,
            "nice_to_have": nice, "size": find_size(text),
            "search_text": re.sub(r"\s+", " ", search).strip()}


# ---- match reasons -------------------------------------------------------------
EQUIVALENT = {"water-resistant": {"water-resistant", "waterproof"},
              "warm": {"warm", "insulated", "wool", "fleece"}}


def _first_need(query: dict) -> str:
    return (query.get("needs") or [""])[0]


def satisfies(attributes: list[str], wanted: str) -> bool:
    return bool(EQUIVALENT.get(wanted, {wanted}) & set(attributes))


def stub_fit(query: dict, row: dict) -> float:
    """Stub-mode ranking nudge: hashed bag-of-words can't tell a kids coat from
    an adult one, so reward the asked-for category and keep kids and adult
    items apart."""
    _, cat = item_phrase(_first_need(query))
    wants_kid = "for a child" in (query.get("inferred_context") or [])
    adj = 0.1 if cat and cat == row["category"] else 0.0
    must = query.get("must_have") or []
    if cat and cat != row["category"] and not any(satisfies(row["attributes"], a) for a in must):
        adj -= 1.0   # a different kind of thing that doesn't even meet the need
    if (row["category"] == "kids") != wants_kid:
        adj -= 1.0   # effectively drops it: never offer a 6T coat to an adult
    return adj


def reason(query: dict, row: dict) -> str:
    """One line (max 12 words) on why an item fits, or what it lacks."""
    must = query.get("must_have") or []
    hits = [a for a in must if satisfies(row["attributes"], a)]
    missing = [a for a in must if a not in hits]
    ctx = (query.get("inferred_context") or [None])[0]
    noun, cat = find_noun(_first_need(query))[:2]
    if cat and cat != row["category"] and row["category"] != "kids":
        feats = " and ".join(hits[:2] or row["attributes"][:2])
        return " ".join(f"Not {noun}, but {feats}".split()[:12]) if feats else f"Not {noun}"
    if must and not missing:
        lead = " and ".join(hits[:2]).capitalize()
        text = f"{lead}, built for {ctx}" if ctx else f"{lead}, just what you asked for"
    elif hits:
        text = f"{' and '.join(hits[:2]).capitalize()}, but not {missing[0]}"
    elif must:
        feats = " and ".join(row["attributes"][:2])
        text = f"{feats.capitalize()}, but not {missing[0]}" if feats else f"Not {missing[0]}"
    else:
        feats = ", ".join(row["attributes"][:2])
        text = f"{row['item'].capitalize()}: {feats}" if feats else row["item"].capitalize()
    return " ".join(text.split()[:12])
