# 07 · Demo script (expo table, ~2 minutes)

Judging expo 1:30 PM, Oct 18. Weights: Technical 25% · Impact 25% · Innovation 20% · UX 15% · Presentation 15%.

**Setup:** laptop 1 shows the app (on the GoDaddy domain); laptop 2 shows the impact dashboard + activity feed full screen. Inventory pre-seeded.

1. **Hook (15 s).** Waste statistic. "Most of this isn't trash; it's just too much effort to give away."
2. **Parse (20 s).** Photograph a real jacket at the table, tag visible. Point at the feed: Gemini reads the brand and size off the tag.
3. **Sell vs donate (20 s).** Tap **Sell**: price range from live eBay listings plus a ready listing. Go back, tap **Donate**: it's searchable now; the dashboard counter ticks up.
4. **Request (35 s).** Type: "snow clothes, moving to Chicago in December." Point at the feed: the agent inferred snow and cold without being told. Show matches with reasons, ideally the jacket just donated. Claim it: reserved, donor notified.
5. **How it works (20 s).** Architecture diagram: deterministic orchestrator, Gemini parser, Modal agents and embeddings, pgvector + hypertable + continuous aggregate on Tiger Data.
6. **Close (10 s).** Impact dashboard. Stretch features if built (Shopstr listing, 30-day rule, kiosk). Sponsor tracks used.

**Backup:** if the network or a model fails, switch the backend to stub mode (unset keys) or play the recorded video.

## Devpost checklist (due 12:00 PM CDT)

- [ ] Project name (replace "Rehome" placeholder if changing)
- [ ] Description (adapt `01-overview.md`)
- [ ] Technologies: SvelteKit, FastAPI, Gemini API, Modal, Tiger Data (pgvector, TimescaleDB), eBay Browse API, Vultr/DigitalOcean, GoDaddy Registry, Nostr (if shown)
- [ ] Working demo link (GoDaddy domain)
- [ ] Demo video (≤ 3 min)
- [ ] Repo link, visible to judges, no keys committed
- [ ] Team members
- [ ] Tracks: Environmental & Sustainability, Modal, [MLH] Tiger Data, [MLH] Gemini API, [MLH] Vultr or DigitalOcean, [MLH] GoDaddy Registry (+ Hardware if kiosk built)
- [ ] After the event: DEV Writing Challenge post
