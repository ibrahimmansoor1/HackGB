"""Listing preview pages (HTML) for the demo screen. Data comes from the
orchestrator, the same as GET /api/listings; these pages just render it, so
the demo doesn't depend on Shopstr's site being up.

    /listings            every listing, newest first
    /listings/{item_id}  one item's latest listing
"""
from html import escape

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.agents import orchestrator
from app.schemas import ListingWithItem

router = APIRouter(tags=["pages"])

STYLE = """
:root { --bg:#f6f5f1; --card:#fff; --ink:#1c1c1c; --muted:#5f6368; --line:#e3e1db;
        --ok:#1f7a4d; --okbg:#e3f3ea; --warn:#8a5a00; --warnbg:#fdf1d8; --off:#6b6b6b;
        --offbg:#ececec; --link:#1f5fa8; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#141414; --card:#1f1f1f; --ink:#f1f1f1; --muted:#a8a8a8; --line:#333;
          --ok:#7fd8a6; --okbg:#173326; --warn:#f3c56b; --warnbg:#3a2d10; --off:#bdbdbd;
          --offbg:#2c2c2c; --link:#8ab8f0; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:18px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 2rem; margin: 0 0 4px; }
.sub { color: var(--muted); margin: 0 0 28px; }
.grid { display:grid; gap:20px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
.card { background:var(--card); border:1px solid var(--line); border-radius:14px; overflow:hidden;
        display:flex; flex-direction:column; color:inherit; text-decoration:none; }
.card img, .hero img { width:100%; aspect-ratio:1; object-fit:cover; display:block;
                       background:var(--line); }
.body { padding:16px 18px 18px; display:flex; flex-direction:column; gap:8px; }
.title { font-weight:650; font-size:1.15rem; }
.price { font-size:1.6rem; font-weight:700; }
.meta { color:var(--muted); font-size:.95rem; }
.badge { display:inline-block; padding:3px 10px; border-radius:999px; font-size:.85rem;
         font-weight:600; width:fit-content; }
.live { color:var(--ok); background:var(--okbg); }
.dry { color:var(--warn); background:var(--warnbg); }
.expired { color:var(--off); background:var(--offbg); }
.hero { display:grid; gap:28px; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
.hero img { border-radius:14px; border:1px solid var(--line); }
.desc { white-space:pre-line; }
.links { display:flex; flex-wrap:wrap; gap:12px; margin-top:8px; }
.links a { color:var(--link); font-weight:600; }
.chips { display:flex; flex-wrap:wrap; gap:6px; }
.chip { border:1px solid var(--line); border-radius:999px; padding:2px 10px; font-size:.85rem; }
.back { color:var(--link); text-decoration:none; display:inline-block; margin-bottom:16px; }
.empty { color:var(--muted); padding:40px 0; }
@media (max-width: 720px) { .hero { grid-template-columns: 1fr; } }
"""


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title><style>{STYLE}</style></head>
<body><main>{body}</main></body></html>""")


def _badge(lst: ListingWithItem) -> str:
    if lst.status == "expired":
        return '<span class="badge expired">Expired · back in the donation pool</span>'
    if lst.dry_run:
        return '<span class="badge dry">Dry run · not published</span>'
    n = len(lst.relays_accepted)
    return f'<span class="badge live">Live on Nostr · {n} relay{"s" if n != 1 else ""}</span>'


def _img(lst: ListingWithItem) -> str:
    if not lst.item.image_url:
        return ""
    return f'<img src="{escape(lst.item.image_url)}" alt="{escape(lst.item.summary)}">'


def _title(lst: ListingWithItem) -> str:
    it = lst.item
    name = f"{it.color} {it.item}".strip()
    return name[:1].upper() + name[1:] + (f", size {it.size}" if it.size else "")


@router.get("/listings", response_class=HTMLResponse, include_in_schema=False)
async def storefront():
    rows = orchestrator.listings()
    cards = "".join(f"""
<a class="card" href="/listings/{escape(lst.item_id)}">
  {_img(lst)}
  <div class="body">
    <div class="title">{escape(_title(lst))}</div>
    <div class="price">${lst.price:g}</div>
    <div class="meta">{escape(lst.item.condition)} · {escape(lst.item.zip)}</div>
    {_badge(lst)}
  </div>
</a>""" for lst in rows)
    body = (f'<h1>Rehome marketplace</h1><p class="sub">Unsold donations listed on Nostr '
            f'(NIP-99). {len(rows)} listing{"s" if len(rows) != 1 else ""}.</p>')
    body += f'<div class="grid">{cards}</div>' if rows else \
        '<p class="empty">Nothing listed yet. List an item with POST /api/items/{id}/list.</p>'
    return _page("Rehome marketplace", body)


@router.get("/listings/{item_id}", response_class=HTMLResponse, include_in_schema=False)
async def listing_page(item_id: str):
    lst = orchestrator.listing_for_item(item_id)
    if lst is None:
        raise HTTPException(404, f"{item_id} has not been listed.")
    it = lst.item
    chips = "".join(f'<span class="chip">{escape(a)}</span>' for a in it.attributes)
    links = (f'<a href="{escape(lst.url)}" target="_blank" rel="noopener">Open on Shopstr ↗</a>'
             f'<a href="{escape(lst.nostr_url)}" target="_blank" rel="noopener">'
             f'View raw Nostr listing ↗</a>') if not lst.dry_run else \
        '<span class="meta">Dry run: signed locally, not sent to relays.</span>'
    relays = ", ".join(r.removeprefix("wss://") for r in lst.relays_accepted) or "none"
    body = f"""<a class="back" href="/listings">← All listings</a>
<div class="hero">
  <div>{_img(lst)}</div>
  <div class="body">
    {_badge(lst)}
    <h1>{escape(_title(lst))}</h1>
    <div class="price">${lst.price:g} <span class="meta">USD</span></div>
    <div class="meta">{escape(it.condition)} · {escape(it.category)} · zip {escape(it.zip)}</div>
    <div class="chips">{chips}</div>
    <p class="desc">{escape(it.summary)}</p>
    <p class="meta">Buying secondhand keeps this out of a landfill. If it doesn't sell in
      30 days, Rehome gives it free to a neighbor who needs it.</p>
    <div class="meta">Listed {lst.listed_at:%b %d, %Y %H:%M} UTC · expires
      {lst.expires_at:%b %d} · relays: {escape(relays)}</div>
    <div class="links">{links}</div>
  </div>
</div>"""
    return _page(f"{_title(lst)} · Rehome", body)
