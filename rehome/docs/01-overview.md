# 01 · Overview

Built at **HackGB 2026** (UW–Green Bay, 24 hours). Devpost deadline: **12:00 PM CDT, Sunday Oct 18, 2026**; judging expo 1:30 PM.

## Problem

A large share of usable clothing and household goods ends up in landfills. The main reason isn't that nobody wants them; it's friction. Selling or donating properly means photographing, describing, pricing, listing, answering messages, and driving somewhere. Most people don't have the time.

The other side has friction too. People who need things (and the organizations serving them) have to hunt through thrift stores and marketplaces with no guarantee of finding the right item.

> TODO (presentation owner): add 2–3 sourced statistics on textile and household waste for the opening slide.

## Solution

Two entry points and a team of AI agents in between.

- **Donors** upload a photo, a short text, or both. The **input parser agent** (Gemini vision) turns it into a structured item, reading brand and size from tags when visible. The donor then picks:
  - **Sell:** the **pricing agent** looks up comparable eBay listings and returns a suggested price range plus a ready-to-post listing draft. *(Stretch: post it to Nostr so it shows on Shopstr; if unsold after 30 days, it moves to the donation pool.)*
  - **Donate:** the item is embedded and saved, and becomes searchable by requesters right away.
- **Requesters** describe a need casually ("snow clothes, moving to Chicago in December"). The **requester agent** infers what they didn't say (cold, snow → insulated, water-resistant), the system runs a vector search over donated items, and returns ranked matches with a one-line reason each. The requester claims one; the item is reserved and the donor is notified.
- An **impact dashboard** shows live stats (items rehomed, by category, over time) and the agent activity feed.

## One-line pitch

One photo to sell or give something away; one sentence to find what you need. Agents handle everything in between.

## What makes it technically interesting

- **Multimodal input:** a vision model turns a photo (including clothing tags) into structured data.
- **Agents do the donor's chores:** a concierge agent (LangGraph on a Modal tool-calling model) takes over after the upload: it asks the pricing agent what the item is worth, asks the matchmaker who nearby needs it, then lists it on Shopstr or donates it and explains why. Specialist agents (parser on Gemini; pricing, requester, reasons on Modal) are pure prompt → JSON functions behind a deterministic orchestrator that owns the data and logs every step.
- **Contextual matching:** the requester agent expands vague intent into concrete attributes from the same vocabulary the parser uses, so both sides line up in vector space (pgvector).
- **Real price comps:** the pricing agent grounds its suggestion in live eBay listings.
- **Time-series impact:** every agent step is an event in a Tiger Data hypertable; a continuous aggregate powers the live dashboard.

## Prize tracks

| Track | How we qualify |
|---|---|
| Best Environmental & Sustainability Hack | Keeps goods out of landfill; impact dashboard |
| Best Use of Modal | Requester + pricing LLMs and embeddings run on Modal |
| [MLH] Best Use of Tiger Data | pgvector matching + events hypertable + continuous aggregate |
| [MLH] Best Use of Gemini API | Input parser (vision, tag reading) |
| [MLH] Vultr *or* DigitalOcean | Backend deployment (pick one) |
| [MLH] GoDaddy Registry | Frontend domain |
| [MLH] DEV Writing Challenge | Post-event write-up |
| Best Hardware Hack *(stretch)* | Kiosk: webcam + distance sensor |

Skipped as forced fits: Solana, Presage, Lovable.
