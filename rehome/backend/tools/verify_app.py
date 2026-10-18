"""Streamlit page for clicking through every backend feature by hand.

Talks to a running backend over HTTP only (same contract as the frontend,
docs/04). From backend/ with the venv active:

    uvicorn app.main:app --port 8000          # terminal 1
    streamlit run tools/verify_app.py         # terminal 2

Set REHOME_API to point at another backend (default http://localhost:8000).
"""
import os

import httpx
import streamlit as st

st.set_page_config(page_title="Rehome verify", layout="wide")
api = st.sidebar.text_input("Backend URL", os.getenv("REHOME_API", "http://localhost:8000"))
ss = st.session_state


def call(method: str, path: str, **kw):
    """Make a request, show errors inline, return the JSON body or None."""
    try:
        r = httpx.request(method, f"{api.rstrip('/')}{path}", timeout=90, **kw)
    except httpx.HTTPError as e:
        st.error(f"Can't reach {api}: {e}")
        return None
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 400:
        st.error(f"{method} {path} → {r.status_code}: {body.get('detail', r.text)}")
        return None
    return body


# ---- sidebar: health + demo helpers ------------------------------------------
if st.sidebar.button("Check health") or "health" not in ss:
    ss.health = call("GET", "/api/health")
if ss.health:
    st.sidebar.write(f"**db:** {ss.health['db']} · **stubs:** {ss.health['stubs']}")
if st.sidebar.button("Seed demo inventory"):
    out = call("POST", "/api/admin/seed")
    if out is not None:
        st.sidebar.success(f"Seeded {out['seeded']} items")
if st.sidebar.button("Simulate 30 days (expire listings)"):
    out = call("POST", "/api/admin/simulate-expiry")
    if out is not None:
        st.sidebar.success(f"Back in the donation pool: {out['expired'] or 'nothing'}")

st.title("Rehome · feature check")
donate_tab, request_tab, inventory_tab, impact_tab, feed_tab = st.tabs(
    ["Donor: parse → sell / donate", "Requester: match → accept", "Inventory & listings",
     "Impact", "Activity feed"])

# ---- donor path ----------------------------------------------------------------
with donate_tab:
    with st.form("parse"):
        photos = st.file_uploader("Photos", type=["jpg", "jpeg", "png", "webp"],
                                  accept_multiple_files=True)
        text = st.text_area("Description", "Black puffer jacket, hooded, water-resistant, size M")
        zip_code = st.text_input("Zip", "54311")
        if st.form_submit_button("Parse"):
            files = [("images", (p.name, p.getvalue(), p.type)) for p in photos or []]
            ss.draft = call("POST", "/api/items/parse", data={"zip": zip_code, "text": text},
                            files=files or None)
            for key in ("quote", "donated", "handled"):
                ss.pop(key, None)

    draft = ss.get("draft")
    if draft:
        st.subheader(f"Draft {draft['draft_id']}")
        left, right = st.columns([1, 2])
        if draft.get("image_url"):
            left.image(draft["image_url"], width=220)
        right.json(draft["item"])
        st.markdown("**Let the agents handle it** (concierge agent, LangGraph)")
        pref_col, go_col = st.columns([2, 1])
        pref = pref_col.radio("Donor preference", ["auto", "sell", "donate"], horizontal=True)
        if go_col.button("Hand it to the concierge", type="primary"):
            ss.handled = call("POST", f"/api/items/{draft['draft_id']}/handle",
                              json={"preference": pref})
        if ss.get("handled"):
            h = ss.handled
            st.success(h["summary"])
            st.write(f"**{h['action']}** `{h['item_id']}` · decided by **{h['brain']}** · "
                     f"tools: {' → '.join(h['steps'])}")
            if h["waiting_requests"]:
                st.write(f"Offered to: {', '.join(h['waiting_requests'])}")
            if h["listing"]:
                st.write(f"Listing: ${h['listing']['price']:g} · {h['listing']['url']}")
        st.markdown("**Or do it by hand**")
        sell, donate = st.columns(2)
        if sell.button("Sell: get a price"):
            ss.quote = call("POST", f"/api/items/{draft['draft_id']}/sell")
        pickup = donate.text_input("Pickup zip (optional)")
        if donate.button("Donate it"):
            ss.donated = call("POST", f"/api/items/{draft['draft_id']}/donate",
                              json={"pickup_zip": pickup} if pickup else {})
        if ss.get("quote"):
            q = ss.quote
            p = q["suggested_price"]
            label = "currently listed for" if q["basis"] == "active listings" else "estimate"
            st.metric(f"Suggested price ({label})", f"${p['low']:g}–{p['high']:g}")
            st.write(f"**{q['listing_draft']['title']}**  \n{q['listing_draft']['description']}")
            if q["comps"]:
                st.dataframe(q["comps"], use_container_width=True)
        if ss.get("donated"):
            st.success(f"{ss.donated['message']} ({ss.donated['item_id']})")

# ---- requester path --------------------------------------------------------------
with request_tab:
    with st.form("request"):
        need = st.text_area("What do you need?", "need a warm coat, moving to Chicago in December")
        rzip = st.text_input("Zip", "60601")
        if st.form_submit_button("Find matches"):
            ss.req = call("POST", "/api/requests", json={"text": need, "zip": rzip})
            ss.pop("accepted", None)

    req = ss.get("req")
    if req:
        st.write(f"**{req['request_id']}** · status `{req['status']}`")
        st.json(req["query"], expanded=False)
        if not req["matches"]:
            st.info("No match above the threshold; the request stays open.")
        for m in req["matches"]:
            cols = st.columns([1, 4, 1])
            if m["item"].get("image_url"):
                cols[0].image(m["item"]["image_url"], width=90)
            cols[1].write(f"**#{m['rank']} {m['title']}** · score {m['score']}  \n{m['reason']}"
                          f"  \n`{m['item_id']}` · {m['item']['status']} · zip {m['item']['zip']}")
            if cols[2].button("Claim", key=f"claim-{m['item_id']}"):
                ss.accepted = call("POST", "/api/matches/accept",
                                   json={"request_id": req["request_id"], "item_id": m["item_id"]})
        if ss.get("accepted"):
            st.success(f"{ss.accepted['match_id']}: {ss.accepted['handoff']['message']}")

# ---- inventory + marketplace -------------------------------------------------------
with inventory_tab:
    status = st.selectbox("Status", ["available", "listed", "reserved", "donated", "(all)"])
    items = call("GET", "/api/items" + ("" if status == "(all)" else f"?status={status}"))
    if items is not None:
        rows = [{k: it[k] for k in ("id", "item", "brand", "color", "size", "condition",
                                    "category", "status", "zip")} for it in items["items"]]
        st.write(f"{len(rows)} items")
        st.dataframe(rows, use_container_width=True)
        listable = [r["id"] for r in rows if r["status"] == "available"]
        if listable:
            pick = st.selectbox("List on Shopstr (Nostr; dry run unless configured)", listable)
            if st.button("List it"):
                out = call("POST", f"/api/items/{pick}/list")
                if out:
                    st.success(f"Listed at ${out['listing']['price']:g} · dry run: "
                               f"{out['listing']['dry_run']} · {out['listing']['url']}")
    listings = call("GET", "/api/listings")
    if listings and listings["listings"]:
        st.subheader("Listings")
        st.dataframe(listings["listings"], use_container_width=True)

# ---- impact ---------------------------------------------------------------------------
with impact_tab:
    impact = call("GET", "/api/impact")
    if impact:
        cols = st.columns(3)
        for i, (k, v) in enumerate(impact["totals"].items()):
            cols[i % 3].metric(k.replace("_", " "), v)
        if impact["by_category"]:
            st.dataframe(impact["by_category"], use_container_width=True)
        if impact["hourly"]:
            st.dataframe(impact["hourly"], use_container_width=True)

# ---- activity feed ---------------------------------------------------------------------
with feed_tab:
    st.button("Refresh")
    events, after = [], 0
    while True:   # the API pages at 50
        page = call("GET", f"/api/events?after={after}")
        if not page or not page["events"]:
            break
        events += page["events"]
        after = page["events"][-1]["id"]
    st.write(f"{len(events)} events, newest first")
    st.dataframe([{k: e[k] for k in ("id", "agent", "event_type", "category", "message",
                                     "created_at")} for e in reversed(events)],
                 use_container_width=True)
