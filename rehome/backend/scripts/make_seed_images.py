"""Draw the demo seed photos into static/seed/ (one PNG per seed item).

    uv run --with pillow python scripts/make_seed_images.py

Flat cards (item color + name), not real photos: clear on a projector and
safe to publish. Re-run after editing app/seed_data.py.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.seed_data import SEED_ITEMS  # noqa: E402

OUT = ROOT / "static" / "seed"
SIZE = 480
COLORS = {"black": "#2b2b2b", "olive": "#6b7240", "navy": "#24345c", "yellow": "#e8c13a",
          "brown": "#7a5233", "gray": "#8a8f96", "tan": "#b89468", "red": "#b8332e",
          "green": "#3f7a4f", "white": "#e9e7e2", "blue": "#3d6fb4", "pink": "#e58fb0",
          "beige": "#d8c9a8", "silver": "#b9bec4"}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def card(color: str, item: str, category: str) -> Image.Image:
    bg = COLORS.get(color, "#888888")
    r, g, b = (int(bg[i:i + 2], 16) for i in (1, 3, 5))
    ink = "#111111" if (r * 299 + g * 587 + b * 114) / 1000 > 150 else "#ffffff"
    img = Image.new("RGB", (SIZE, SIZE), bg)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((24, 24, SIZE - 24, SIZE - 24), radius=28, outline=ink, width=4)
    big, small = ImageFont.truetype(FONT, 44), ImageFont.truetype(FONT, 26)
    words, lines = item.split(), []
    for w in words:
        if lines and d.textlength(f"{lines[-1]} {w}", font=big) < SIZE - 96:
            lines[-1] += f" {w}"
        else:
            lines.append(w)
    y = SIZE / 2 - 30 * len(lines)
    for line in lines:
        d.text((SIZE / 2, y), line.capitalize() if line == lines[0] else line,
               font=big, fill=ink, anchor="mt")
        y += 58
    d.text((SIZE / 2, SIZE - 70), f"{color} · {category}", font=small, fill=ink, anchor="mt")
    d.text((SIZE / 2, 60), "Rehome demo", font=small, fill=ink, anchor="mt")
    return img


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for cat, item, color, *_rest, photo in SEED_ITEMS:
        card(color, item, cat).save(OUT / f"{photo}.png", optimize=True)
    print(f"wrote {len(SEED_ITEMS)} images to {OUT}")
